"""Workspace directory management for OR-Intern.

Each session gets its own persistent workspace directory under outputs/.
All tools in a session write files to the same workspace, enabling
multi-turn collaboration where the LLM can reference and build upon
previous outputs.

Directory structure:
    outputs/
      <session_id_prefix>/
        model_v1.py
        model_v2_relaxed.py
        variables_bar.png
        report_final.md
        .workspace_state.json
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_OUTPUTS_ROOT = Path(__file__).parent.parent.parent / "outputs"
_STATE_FILENAME = ".workspace_state.json"


def get_workspace_dir(session: Any = None) -> Path:
    """Get the workspace directory for the current session.

    Each session has a single persistent workspace directory where
    all tool outputs are written. The directory name uses the format:
    <YYYY-MM-DD>_<session_id_prefix> for easy identification.

    Parameters
    ----------
    session : Session or None
        Active session. When None (e.g., in tests), falls back to a
        default workspace directory.

    Returns
    -------
    Path
        Absolute path to the workspace directory, guaranteed to exist.
    """
    if session is not None:
        session_id = getattr(session, "session_id", None)
        if session_id:
            date_prefix = datetime.now().strftime("%Y-%m-%d")
            prefix = session_id[:8]
            ws_dir = _OUTPUTS_ROOT / f"{date_prefix}_{prefix}"
            ws_dir.mkdir(parents=True, exist_ok=True)
            return ws_dir

    ws_dir = _OUTPUTS_ROOT / "default"
    ws_dir.mkdir(parents=True, exist_ok=True)
    return ws_dir


def get_run_dir() -> Path:
    """Backward-compatible alias for get_workspace_dir(None).

    Used by tests that monkeypatch this function.
    """
    return get_workspace_dir(None)


def clear_run_marker() -> None:
    """No-op — retained for backward compatibility.

    Workspace directories are session-scoped, not run-scoped,
    so there is no marker to clear.
    """
    pass


# ── Workspace State Management ──


def _state_file(workspace_dir: Path) -> Path:
    """Return path to the workspace state file."""
    return workspace_dir / _STATE_FILENAME


def load_workspace_state(workspace_dir: Path) -> dict[str, Any]:
    """Load the workspace state from the state file.

    Returns
    -------
    dict
        Workspace state with 'files' list and metadata.
    """
    state_path = _state_file(workspace_dir)
    if not state_path.exists():
        return {"files": [], "created": datetime.now().isoformat()}
    try:
        with open(state_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load workspace state: %s", e)
        return {"files": [], "created": datetime.now().isoformat()}


def save_workspace_state(workspace_dir: Path, state: dict[str, Any]) -> None:
    """Save the workspace state to the state file."""
    state_path = _state_file(workspace_dir)
    try:
        state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        logger.debug("Failed to save workspace state: %s", e)


def record_file(
    workspace_dir: Path,
    filename: str,
    *,
    file_type: str = "unknown",
    tool: str = "",
    turn: int | None = None,
    note: str = "",
) -> Path:
    """Record a file in the workspace state.

    Parameters
    ----------
    workspace_dir : Path
        Workspace directory.
    filename : str
        Name of the file (relative to workspace).
    file_type : str
        Type of file (pyomo_model, cvxpy_model, chart, report, data).
    tool : str
        Name of the tool that created the file.
    turn : int or None
        Conversation turn number.
    note : str
        Optional note about the file.

    Returns
    -------
    Path
        Full path to the file.
    """
    state = load_workspace_state(workspace_dir)

    existing_names = {f["name"] for f in state.get("files", [])}
    file_entry = {
        "name": filename,
        "type": file_type,
        "tool": tool,
        "created": datetime.now().isoformat(),
        "note": note,
    }
    if turn is not None:
        file_entry["turn"] = turn

    if filename in existing_names:
        state["files"] = [
            f for f in state["files"] if f["name"] != filename
        ]

    state["files"].append(file_entry)
    save_workspace_state(workspace_dir, state)

    return workspace_dir / filename


def list_workspace_files(workspace_dir: Path) -> str:
    """Generate a human-readable summary of workspace files.

    Used for injecting into the system prompt so the LLM knows
    what files are available in the workspace.

    Returns
    -------
    str
        Markdown-formatted file listing, or empty string if workspace
        is empty.
    """
    if not workspace_dir.exists():
        return ""

    state = load_workspace_state(workspace_dir)
    files = state.get("files", [])

    actual_files = [
        f for f in workspace_dir.iterdir()
        if f.is_file() and f.name != _STATE_FILENAME
    ]

    if not actual_files and not files:
        return ""

    lines = [
        f"Workspace: {workspace_dir}/",
        "",
    ]

    if files:
        for f in files:
            size = ""
            file_path = workspace_dir / f["name"]
            if file_path.exists():
                size_kb = file_path.stat().st_size / 1024
                size = f" ({size_kb:.1f} KB)"
            note = f" — {f['note']}" if f.get("note") else ""
            lines.append(f"  - {f['name']}{size} [{f.get('type', 'file')}]{note}")

    recorded_names = {f["name"] for f in files}
    unrecorded = [
        f for f in actual_files if f.name not in recorded_names
    ]
    if unrecorded:
        for f in sorted(unrecorded, key=lambda x: x.stat().st_mtime):
            size_kb = f.stat().st_size / 1024
            lines.append(f"  - {f.name} ({size_kb:.1f} KB)")

    return "\n".join(lines)


def suggest_filename(workspace_dir: Path, base: str, ext: str) -> str:
    """Suggest a unique filename, adding version suffix if needed.

    If ``base.ext`` already exists, tries ``base_v2.ext``, ``base_v3.ext``, etc.

    Parameters
    ----------
    workspace_dir : Path
        Workspace directory.
    base : str
        Base filename without extension (e.g., "model").
    ext : str
        File extension including the dot (e.g., ".py").

    Returns
    -------
    str
        A filename that does not exist in the workspace.
    """
    candidate = f"{base}{ext}"
    if not (workspace_dir / candidate).exists():
        return candidate

    version = 2
    while True:
        candidate = f"{base}_v{version}{ext}"
        if not (workspace_dir / candidate).exists():
            return candidate
        version += 1
        if version > 999:
            ts = time.strftime("%H%M%S")
            return f"{base}_{ts}{ext}"
