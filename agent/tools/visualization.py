"""visualization tool for OR-Intern Phase 2.

Generates charts from solve results: variable values bar chart,
constraint utilization, objective sensitivity plot.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _generate_gap_chart(gap_data: list[dict], chart_path: str) -> str:
    """Generate solver progress gap-vs-time chart."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    if not gap_data:
        return ""

    times = [d.get('time', d.get('t', 0)) for d in gap_data]
    gaps = [d.get('gap', 0) for d in gap_data]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Gap vs time
    ax1.plot(times, gaps, 'o-', color='#E74C3C', linewidth=2, markersize=4)
    ax1.set_title('Optimality Gap vs Time', fontsize=13, fontweight='bold')
    ax1.set_xlabel('Time (s)', fontsize=11)
    ax1.set_ylabel('Gap', fontsize=11)
    ax1.grid(alpha=0.3)
    ax1.set_yscale('log')

    # Convergence: bounds
    if any('bound' in d for d in gap_data):
        bounds = [d.get('bound', d.get('obj', 0)) for d in gap_data]
        ax2.plot(times, bounds, 'o-', color='#3498DB', linewidth=2, markersize=4)
        ax2.set_title('Bound Convergence', fontsize=13, fontweight='bold')
        ax2.set_xlabel('Time (s)', fontsize=11)
        ax2.set_ylabel('Bound Value', fontsize=11)
        ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_variable_chart(variables: dict, objective: float,
                              chart_path: str) -> str:
    """Generate a bar chart of variable values."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    names = list(variables.keys())
    values = list(variables.values())

    # Chinese-friendly colors (red for positive)
    colors = ['#E74C3C' if v > 0 else '#27AE60' for v in values]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(names, values, color=colors, edgecolor='white', linewidth=0.5)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.02,
                f'{val:.2f}', ha='center', va='bottom', fontweight='bold')

    ax.set_title(f'Optimal Solution (Objective: {objective:.2f})', fontsize=14, fontweight='bold')
    ax.set_ylabel('Value', fontsize=12)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_sensitivity_chart(param_data: list[dict], var_name: str,
                                 chart_path: str) -> str:
    """Generate sensitivity analysis line chart."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    if not param_data:
        return ""

    deltas = [d.get('delta', 0) for d in param_data]
    objs = [d.get('objective', 0) for d in param_data]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(deltas, objs, 'o-', color='#3498DB', linewidth=2, markersize=5)
    ax.axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    ax.axhline(y=max(objs) if objs else 0, color='#E74C3C',
               linestyle='--', alpha=0.3, label='Max')

    ax.set_title(f'Sensitivity: Objective Coefficient of {var_name}', fontsize=14, fontweight='bold')
    ax.set_xlabel(f'Delta in {var_name} coefficient', fontsize=12)
    ax.set_ylabel('Objective Value', fontsize=12)
    ax.grid(alpha=0.3)
    ax.legend()

    plt.tight_layout()
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path


# ── Tool spec and handler ──

VISUALIZATION_TOOL_SPEC = {
    "name": "visualization",
    "description": (
        "Generate visual charts from optimization results. "
        "Creates bar charts of variable values, constraint utilization, "
        "and sensitivity plots. Output: PNG image file path."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "chart_type": {
                "type": "string",
                "enum": ["variables", "sensitivity", "all"],
                "description": "Chart type to generate",
                "default": "all",
            },
            "variables": {
                "type": "object",
                "description": 'Variable values, e.g. {"x": 10.0, "y": 0.0}',
            },
            "objective": {
                "type": "number",
                "description": "Objective function value",
            },
            "param_data": {
                "type": "array",
                "description": 'Parametric data for sensitivity chart: [{"delta": 0, "objective": 30}, ...]',
            },
            "var_name": {
                "type": "string",
                "description": "Variable name for sensitivity chart",
                "default": "x",
            },
            "gap_data": {
                "type": "array",
                "description": 'Solver progress data: [{"time": 0.1, "gap": 0.5, "bound": 25.0}, ...]',
            },
        },
    },
}


async def visualization_handler(args: dict[str, Any]) -> tuple[str, bool]:
    """Handler for visualization tool."""
    chart_type = args.get("chart_type", "all")
    variables = args.get("variables", {})
    objective = args.get("objective", 0)
    param_data = args.get("param_data", [])
    var_name = args.get("var_name", "x")
    gap_data = args.get("gap_data", [])

    tmpdir = Path(tempfile.gettempdir()) / "or-intern" / "charts"
    tmpdir.mkdir(parents=True, exist_ok=True)

    charts = []

    try:
        if chart_type in ("variables", "all") and variables:
            path = str(tmpdir / "variables.png")
            _generate_variable_chart(variables, objective, path)
            charts.append(("Variable Values", path))

        if chart_type in ("sensitivity", "all") and param_data:
            path = str(tmpdir / "sensitivity.png")
            _generate_sensitivity_chart(param_data, var_name, path)
            charts.append(("Sensitivity Analysis", path))

        if gap_data and chart_type in ("all",):
            path = str(tmpdir / "gap_progress.png")
            _generate_gap_chart(gap_data, path)
            charts.append(("Solver Progress", path))

        if not charts:
            return "No data provided for visualization", True

        result = "## Visualization Results\n\n"
        for title, path in charts:
            result += f"- **{title}**: `{path}`\n"

        return result, False

    except Exception as e:
        return f"Error generating chart: {e}", True
