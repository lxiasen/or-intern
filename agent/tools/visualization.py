"""visualization tool for OR-Intern Phase 2.

Generates charts from solve results: variable values bar chart,
constraint utilization, objective sensitivity plot.
"""

import logging
from pathlib import Path
from typing import Any

from agent.tools._output_dir import get_run_dir

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


def _generate_constraint_heatmap(constraints: dict, chart_path: str) -> str:
    """Generate constraint tightness heatmap.

    Shows binding/non-binding constraints and their slack values.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    if not constraints:
        return ""

    names = list(constraints.keys())
    slacks = []
    for name in names:
        val = constraints[name]
        if isinstance(val, (int, float)):
            slacks.append(abs(val))
        else:
            slacks.append(0.0)

    fig, ax = plt.subplots(figsize=(max(8, len(names) * 0.8), 6))

    # Create heatmap data
    data = np.array(slacks).reshape(1, -1)
    cmap = plt.cm.RdYlGn  # Red (tight) to Green (slack)
    im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=0, vmax=max(slacks) if slacks else 1)

    # Labels
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=45, ha='right')
    ax.set_yticks([0])
    ax.set_yticklabels(['Slack'])

    # Add text annotations
    for i in range(len(names)):
        val = slacks[i]
        color = 'white' if val < max(slacks) * 0.3 else 'black'
        ax.text(i, 0, f'{val:.4f}', ha='center', va='center', color=color, fontweight='bold')

    ax.set_title('Constraint Tightness Heatmap', fontsize=14, fontweight='bold')
    plt.colorbar(im, label='Slack (lower = tighter)')

    plt.tight_layout()
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_pareto_front(objectives: list[dict], chart_path: str) -> str:
    """Generate Pareto front visualization for multi-objective problems.

    Args:
        objectives: List of dicts with 'obj1', 'obj2', and optional 'label'
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    if not objectives or len(objectives) < 2:
        return ""

    obj1_vals = [d.get('obj1', 0) for d in objectives]
    obj2_vals = [d.get('obj2', 0) for d in objectives]
    labels = [d.get('label', f'S{i+1}') for i, d in enumerate(objectives)]

    fig, ax = plt.subplots(figsize=(10, 7))

    # Sort by first objective for line plot
    sorted_pairs = sorted(zip(obj1_vals, obj2_vals, labels))
    obj1_sorted = [p[0] for p in sorted_pairs]
    obj2_sorted = [p[1] for p in sorted_pairs]

    # Plot Pareto front line
    ax.plot(obj1_sorted, obj2_sorted, 'b-', linewidth=2, alpha=0.5, label='Pareto Front')

    # Plot points
    scatter = ax.scatter(obj1_vals, obj2_vals, c='#E74C3C', s=100, zorder=5, edgecolors='white', linewidth=2)

    # Add labels
    for i, label in enumerate(labels):
        ax.annotate(label, (obj1_vals[i], obj2_vals[i]),
                   textcoords="offset points", xytext=(0, 10),
                   ha='center', fontsize=9)

    ax.set_xlabel('Objective 1', fontsize=12)
    ax.set_ylabel('Objective 2', fontsize=12)
    ax.set_title('Pareto Front - Multi-Objective Optimization', fontsize=14, fontweight='bold')
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
        "Creates bar charts of variable values, constraint tightness heatmap, "
        "Pareto front, gap convergence, and sensitivity plots. Output: PNG image file path."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "chart_type": {
                "type": "string",
                "enum": ["variables", "sensitivity", "heatmap", "pareto", "all"],
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
            "constraints": {
                "type": "object",
                "description": 'Constraint slack values for heatmap, e.g. {"c1": 0.5, "c2": 0.0}',
            },
            "pareto_data": {
                "type": "array",
                "description": 'Pareto front data: [{"obj1": 10, "obj2": 20, "label": "S1"}, ...]',
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
    constraints = args.get("constraints", {})
    pareto_data = args.get("pareto_data", [])

    if chart_type in ("variables", "all") and not variables:
        return "No variable data provided for visualization. Pass `variables` dict, e.g. {\"x\": 10, \"y\": 0}.", True

    # Validate variables values are numeric
    if variables:
        bad = {k: v for k, v in variables.items() if not isinstance(v, (int, float))}
        if bad:
            return f"Variable values must be numeric. Invalid: {bad}", True

    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return "matplotlib is not installed. Run: uv add matplotlib", True

    rundir = get_run_dir()
    charts = []

    try:
        if chart_type in ("variables", "all") and variables:
            path = str(rundir / "variables.png")
            _generate_variable_chart(variables, objective, path)
            charts.append(("Variable Values", path))

        if chart_type in ("sensitivity", "all") and param_data:
            path = str(rundir / "sensitivity.png")
            _generate_sensitivity_chart(param_data, var_name, path)
            charts.append(("Sensitivity Analysis", path))

        if chart_type in ("heatmap", "all") and constraints:
            path = str(rundir / "constraint_heatmap.png")
            _generate_constraint_heatmap(constraints, path)
            charts.append(("Constraint Tightness Heatmap", path))

        if chart_type in ("pareto", "all") and pareto_data:
            path = str(rundir / "pareto_front.png")
            _generate_pareto_front(pareto_data, path)
            charts.append(("Pareto Front", path))

        if gap_data and chart_type in ("all",):
            path = str(rundir / "gap_progress.png")
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
