"""data_handler tool for OR-Intern Phase 1 (completion).

Loads, validates, and converts OR data files (CSV, JSON) into
Pyomo-compatible structures (Param, Set, distance matrices).
"""

import csv
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Loaders ──

def _load_csv(path: str) -> dict:
    """Load CSV and auto-detect structure."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))

    if not reader:
        return {"type": "empty", "data": []}

    header = reader[0]
    rows = reader[1:]

    # Detect: distance matrix (square, numeric, first col is label)
    if len(header) > 1 and all(h == "" or h.isdigit() or h.replace(".", "").isdigit()
                               for h in header[1:]):
        return {
            "type": "matrix",
            "labels": [r[0] for r in rows],
            "data": [[float(c) for c in r[1:]] for r in rows],
            "shape": [len(rows), len(header) - 1],
        }

    # Detect: tabular (named columns)
    data = []
    for row in rows:
        entry = {}
        for i, col in enumerate(header):
            if i < len(row):
                val = row[i].strip()
                try:
                    entry[col.strip()] = float(val) if val else 0.0
                except ValueError:
                    entry[col.strip()] = val
        data.append(entry)

    return {
        "type": "tabular",
        "columns": [c.strip() for c in header],
        "data": data,
        "rows": len(data),
    }


def _load_json(path: str) -> dict:
    """Load JSON data file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return {"type": "list", "data": data, "length": len(data)}

    return {"type": "object", "data": data,
            "keys": list(data.keys()) if isinstance(data, dict) else []}


# ── Generate Pyomo data snippet ──

def _to_pyomo_data(parsed: dict) -> str:
    """Convert parsed data to Pyomo-compatible Python code."""
    dtype = parsed["type"]

    if dtype == "matrix":
        labels = parsed["labels"]
        matrix = parsed["data"]
        lines = [
            "# Pyomo-compatible distance/cost matrix",
            f"# {len(labels)} locations: {', '.join(labels[:10])}",
            "",
            f"I = Set(initialize={labels})",
            "",
            "# Distance/cost dictionary",
            "cost = Param(I, I, initialize={",
        ]
        for i, row in enumerate(matrix[:20]):
            for j, val in enumerate(row[:20]):
                if val != 0:
                    lines.append(f"    ({labels[i]}, {labels[j]}): {val},")
        lines.append("}, default=0)")
        return "\n".join(lines)

    if dtype == "tabular":
        lines = [
            "# Pyomo-compatible tabular data",
            f"# {parsed['rows']} rows, columns: {', '.join(parsed['columns'][:10])}",
            "",
            "# Example usage:",
            f"# data = {{{parsed['columns'][:5]}}}",
        ]
        for i, row in enumerate(parsed["data"][:10]):
            vals = ", ".join(
                f"{parsed['columns'][j]}={val}" for j, val in
                zip(range(len(parsed['columns'])), row.values())
                if j < 5
            )
            lines.append(f"#   row{i}: {vals}")
        return "\n".join(lines)

    if dtype == "list":
        lines = [
            "# Pyomo-compatible list data",
            f"# {parsed['length']} items",
        ]
        for i, item in enumerate(parsed["data"][:10]):
            lines.append(f"#   [{i}] {item}")
        return "\n".join(lines)

    return f"# Pyomo-compatible data: {dtype}"


# ── Tool spec ──

DATA_HANDLER_TOOL_SPEC = {
    "name": "data_handler",
    "description": (
        "Load and validate OR data files (CSV, JSON). "
        "Auto-detects structure: distance/cost matrices, tabular data, "
        "time windows. Converts to Pyomo-compatible Python code. "
        "Use before model_builder to prepare input data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to CSV or JSON data file",
            },
            "operation": {
                "type": "string",
                "enum": ["inspect", "convert"],
                "description": "inspect: show data summary; convert: generate Pyomo code",
                "default": "inspect",
            },
        },
        "required": ["file_path"],
    },
}


async def data_handler_handler(args: dict[str, Any]) -> tuple[str, bool]:
    """Handler for data_handler tool."""
    file_path = args.get("file_path", "")
    operation = args.get("operation", "inspect")

    if not file_path:
        return "Error: No file path provided", True

    fp = Path(file_path)
    if not fp.exists():
        return f"Error: File not found: {file_path}", True

    # Load
    suffix = fp.suffix.lower()
    try:
        if suffix == ".csv":
            parsed = _load_csv(str(fp))
        elif suffix == ".json":
            parsed = _load_json(str(fp))
        else:
            return f"Error: Unsupported format '{suffix}'. Use CSV or JSON.", True
    except Exception as e:
        return f"Error loading file: {e}", True

    # Inspect
    if operation == "inspect":
        result = f"## Data Inspection: {fp.name}\n\n"
        result += f"**Type**: {parsed['type']}\n"

        if parsed["type"] == "matrix":
            result += f"**Shape**: {parsed['shape'][0]}x{parsed['shape'][1]}\n"
            result += f"**Locations**: {len(parsed['labels'])}\n"
            if parsed["data"]:
                row = parsed["data"][0]
                result += f"**Sample row**: {row[:5]}\n"
                result += f"**Value range**: [{min(min(r) for r in parsed['data'])}, "
                result += f"{max(max(r) for r in parsed['data'])}]\n"

        elif parsed["type"] == "tabular":
            result += f"**Rows**: {parsed['rows']}\n"
            result += f"**Columns**: {', '.join(parsed['columns'][:10])}\n"
            if parsed["data"]:
                result += f"**Sample**: {json.dumps(parsed['data'][0], default=str)[:150]}\n"

        elif parsed["type"] == "list":
            result += f"**Items**: {parsed['length']}\n"

        result += f"\nUse `data_handler` with operation='convert' to generate Pyomo code."
        return result, False

    # Convert
    pyomo_code = _to_pyomo_data(parsed)

    # Write to temp file
    tmpdir = Path(tempfile.gettempdir()) / "or-intern"
    tmpdir.mkdir(exist_ok=True)
    code_file = tmpdir / f"data_{fp.stem}.py"
    code_file.write_text(pyomo_code, encoding="utf-8")

    result = f"## Pyomo Data Code\n\n"
    result += f"**Source**: {fp.name}\n"
    result += f"**Type**: {parsed['type']}\n"
    result += f"**Output**: {code_file}\n\n"
    result += f"```python\n{pyomo_code[:1500]}\n```\n"

    if len(pyomo_code) > 1500:
        result += f"\n*(showing first 1500 of {len(pyomo_code)} chars)*"

    return result, False
