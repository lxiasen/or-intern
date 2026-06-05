"""visualization tool for OR-Intern Phase 2.

Generates charts from solve results: variable values bar chart,
constraint utilization, objective sensitivity plot.
"""

import logging
from pathlib import Path
from typing import Any

from agent.tools._output_dir import get_workspace_dir, suggest_filename, record_file

logger = logging.getLogger(__name__)


def _setup_chinese_font():
    """Configure matplotlib to support Chinese characters."""
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    
    # Try common Chinese fonts
    chinese_fonts = [
        'SimHei',           # 黑体
        'Microsoft YaHei',  # 微软雅黑
        'STSong',           # 华文宋体
        'Arial Unicode MS', # Arial Unicode
        'WenQuanYi Micro Hei',  # 文泉驿微米黑
        'Noto Sans CJK SC',     # Noto Sans CJK
    ]
    
    # Find available Chinese font
    available_fonts = [f.name for f in fm.fontManager.ttflist]
    font_found = None
    for font in chinese_fonts:
        if font in available_fonts:
            font_found = font
            break
    
    if font_found:
        plt.rcParams['font.sans-serif'] = [font_found, 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
        logger.debug(f"Using Chinese font: {font_found}")
    else:
        logger.warning("No Chinese font found. Chinese characters may not display correctly.")


def _generate_gap_chart(gap_data: list[dict], chart_path: str,
                        title: str = "Solver Progress",
                        xlabel: str = "Time (s)",
                        ylabel: str = "Gap") -> str:
    """Generate solver progress gap-vs-time chart."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _setup_chinese_font()

    if not gap_data:
        return ""

    times = [d.get('time', d.get('t', 0)) for d in gap_data]
    gaps = [d.get('gap', 0) for d in gap_data]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Gap vs time
    ax1.plot(times, gaps, 'o-', color='#E74C3C', linewidth=2, markersize=4)
    ax1.set_title(f'{title} - Gap vs {xlabel}', fontsize=13, fontweight='bold')
    ax1.set_xlabel(xlabel, fontsize=11)
    ax1.set_ylabel(ylabel, fontsize=11)
    ax1.grid(alpha=0.3)
    ax1.set_yscale('log')

    # Convergence: bounds
    if any('bound' in d for d in gap_data):
        bounds = [d.get('bound', d.get('obj', 0)) for d in gap_data]
        ax2.plot(times, bounds, 'o-', color='#3498DB', linewidth=2, markersize=4)
        ax2.set_title(f'{title} - Bound Convergence', fontsize=13, fontweight='bold')
        ax2.set_xlabel(xlabel, fontsize=11)
        ax2.set_ylabel('Bound Value', fontsize=11)
        ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_variable_chart(variables: dict, objective: float,
                              chart_path: str,
                              title: str = "",
                              xlabel: str = "",
                              ylabel: str = "Value") -> str:
    """Generate a bar chart of variable values."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _setup_chinese_font()

    names = list(variables.keys())
    values = list(variables.values())

    # Chinese-friendly colors (red for positive)
    colors = ['#E74C3C' if v > 0 else '#27AE60' for v in values]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(names, values, color=colors, edgecolor='white', linewidth=0.5)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.02,
                f'{val:.2f}', ha='center', va='bottom', fontweight='bold')

    ax.set_title(title or f'Optimal Solution (Objective: {objective:.2f})', fontsize=14, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=12)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_sensitivity_chart(param_data: list[dict], var_name: str,
                                 chart_path: str,
                                 title: str = "",
                                 xlabel: str = "",
                                 ylabel: str = "Objective Value") -> str:
    """Generate sensitivity analysis line chart."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _setup_chinese_font()

    if not param_data:
        return ""

    deltas = [d.get('delta', 0) for d in param_data]
    objs = [d.get('objective', 0) for d in param_data]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(deltas, objs, 'o-', color='#3498DB', linewidth=2, markersize=5)
    ax.axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    ax.axhline(y=max(objs) if objs else 0, color='#E74C3C',
               linestyle='--', alpha=0.3, label='Max')

    ax.set_title(title or f'Sensitivity: Objective Coefficient of {var_name}', fontsize=14, fontweight='bold')
    ax.set_xlabel(xlabel or f'Delta in {var_name} coefficient', fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.grid(alpha=0.3)
    ax.legend()

    plt.tight_layout()
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_constraint_heatmap(constraints: dict, chart_path: str,
                                  title: str = "Constraint Tightness Heatmap",
                                  xlabel: str = "",
                                  ylabel: str = "Slack") -> str:
    """Generate constraint tightness heatmap.

    Shows binding/non-binding constraints and their slack values.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    _setup_chinese_font()

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
    ax.set_yticklabels([ylabel])

    # Add text annotations
    for i in range(len(names)):
        val = slacks[i]
        color = 'white' if val < max(slacks) * 0.3 else 'black'
        ax.text(i, 0, f'{val:.4f}', ha='center', va='center', color=color, fontweight='bold')

    ax.set_title(title, fontsize=14, fontweight='bold')
    plt.colorbar(im, label='Slack (lower = tighter)')

    plt.tight_layout()
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_pareto_front(objectives: list[dict], chart_path: str,
                            title: str = "Pareto Front",
                            xlabel: str = "Objective 1",
                            ylabel: str = "Objective 2") -> str:
    """Generate Pareto front visualization for multi-objective problems.

    Args:
        objectives: List of dicts with 'obj1', 'obj2', and optional 'label'
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _setup_chinese_font()

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

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(alpha=0.3)
    ax.legend()

    plt.tight_layout()
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_trend_chart(
    series_data: dict[str, list[float]],
    x_labels: list[str],
    chart_path: str,
    title: str = "Trend Analysis",
    xlabel: str = "Period",
    ylabel: str = "Value",
    threshold_lines: dict[str, float] | None = None,
    fill_threshold: float | None = None,
) -> str:
    """Generate multi-subplot trend chart with optional threshold lines.

    Args:
        series_data: {series_name: [value1, value2, ...]}
        x_labels: labels for x-axis
        chart_path: output file path
        title: chart title
        xlabel: x-axis label
        ylabel: y-axis label
        threshold_lines: {line_name: y_value} for horizontal reference lines
        fill_threshold: fill area below this threshold with warning color
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import math
    _setup_chinese_font()

    if not series_data:
        return ""

    n_series = len(series_data)
    n_cols = min(4, n_series)
    n_rows = math.ceil(n_series / n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
    if n_series == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    for idx, (series_name, values) in enumerate(series_data.items()):
        ax = axes[idx]
        ax.plot(range(len(x_labels)), values, 'b-o', linewidth=2, markersize=6)

        # Add threshold lines
        if threshold_lines:
            for line_name, line_val in threshold_lines.items():
                ax.axhline(y=line_val, color='r', linestyle='--', linewidth=1.5,
                           label=f'{line_name}={line_val}')
                if fill_threshold is not None:
                    ax.fill_between(range(len(x_labels)), 0, line_val,
                                   alpha=0.1, color='red')

        # Mark points below threshold
        if fill_threshold is not None and threshold_lines:
            threshold_val = list(threshold_lines.values())[0]
            for i, val in enumerate(values):
                if val < threshold_val:
                    ax.annotate('⚠', xy=(i, val), fontsize=12, color='red',
                               ha='center', va='bottom')

        ax.set_title(series_name, fontsize=10, fontweight='bold')
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if threshold_lines:
            ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
        ax.set_xticks(range(len(x_labels)))
        ax.set_xticklabels(x_labels, rotation=45 if len(x_labels) > 6 else 0)

    # Hide unused subplots
    for idx in range(n_series, len(axes)):
        axes[idx].axis('off')

    plt.suptitle(title, fontsize=16, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_stacked_bar_chart(
    category_data: dict[str, list[float]],
    categories: list[str],
    x_labels: list[str],
    chart_path: str,
    title: str = "Stacked Bar Chart",
    xlabel: str = "Category",
    ylabel: str = "Value",
) -> str:
    """Generate stacked bar chart.

    Args:
        category_data: {category_name: [value1, value2, ...]}
        categories: list of category names
        x_labels: labels for x-axis (groups)
        chart_path: output file path
        title: chart title
        xlabel: x-axis label
        ylabel: y-axis label
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    _setup_chinese_font()

    if not category_data:
        return ""

    fig, ax = plt.subplots(figsize=(14, 8))

    n_categories = len(categories)
    x = np.arange(len(x_labels))
    width = max(0.08, 0.8 / n_categories)
    colors = plt.cm.tab20(np.linspace(0, 1, n_categories))

    bottom = np.zeros(len(x_labels))
    for i, cat in enumerate(categories):
        values = category_data.get(cat, [0] * len(x_labels))
        ax.bar(x, values, width, bottom=bottom, label=cat[:10], color=colors[i])
        bottom += values

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=45 if len(x_labels) > 6 else 0)
    ax.legend(fontsize=7, loc='upper left', bbox_to_anchor=(1.02, 1))
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_scatter_gantt_chart(
    event_data: dict[str, list[float]],
    categories: list[str],
    x_labels: list[str],
    chart_path: str,
    title: str = "Event Timeline",
    xlabel: str = "Period",
    scale_factor: float = 50.0,
    threshold: float = 100.0,
) -> str:
    """Generate scatter-based Gantt chart for event visualization.

    Args:
        event_data: {category_name: [event_value1, event_value2, ...]}
        categories: list of category names
        x_labels: labels for x-axis (time periods)
        chart_path: output file path
        title: chart title
        xlabel: x-axis label
        scale_factor: divisor for scatter point size
        threshold: minimum value to show annotation
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _setup_chinese_font()

    if not event_data:
        return ""

    fig, ax = plt.subplots(figsize=(16, 8))

    for i, cat in enumerate(categories):
        events = event_data.get(cat, [0] * len(x_labels))
        for j in range(len(x_labels)):
            if j < len(events) and events[j] > 0.1:
                ax.scatter(j, i, s=events[j] / scale_factor, c='green', alpha=0.7,
                          edgecolors='darkgreen', linewidth=0.5)
                if events[j] > threshold:
                    ax.annotate(f'{events[j]:.0f}', xy=(j, i), fontsize=7,
                               ha='center', va='center')

    ax.set_yticks(range(len(categories)))
    ax.set_yticklabels([c[:12] for c in categories], fontsize=9)
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, rotation=45 if len(x_labels) > 6 else 0)
    ax.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_pie_chart(
    data: dict[str, float],
    chart_path: str,
    title: str = "Distribution",
    colors_list: list[str] | None = None,
) -> str:
    """Generate pie chart.

    Args:
        data: {label: value}
        chart_path: output file path
        title: chart title
        colors_list: optional list of colors
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _setup_chinese_font()

    if not data:
        return ""

    labels = list(data.keys())
    sizes = list(data.values())

    if not sizes or all(s == 0 for s in sizes):
        return ""

    default_colors = ['#4CAF50', '#2196F3', '#FF5722', '#9C27B0', '#FF9800', '#00BCD4']
    colors = colors_list or default_colors[:len(labels)]

    explode = [0.05] * len(labels)
    if len(explode) > 2:
        explode[-1] = 0.1

    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, texts, autotexts = ax.pie(
        sizes, explode=explode, labels=labels,
        colors=colors, autopct='%1.1f%%',
        startangle=90, textprops={'fontsize': 11}
    )
    for t in autotexts:
        t.set_fontweight('bold')

    ax.set_title(title, fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()
    return chart_path


def _generate_ratio_heatmap(
    value_data: dict[str, list[float]],
    reference_data: dict[str, float],
    categories: list[str],
    x_labels: list[str],
    chart_path: str,
    title: str = "Ratio Heatmap",
    xlabel: str = "Period",
    ylabel: str = "Category",
    value_label: str = "Value",
    ratio_label: str = "Ratio",
    cmap: str = 'RdYlGn_r',
) -> str:
    """Generate heatmap showing ratio of values to reference.

    Args:
        value_data: {category: [value1, value2, ...]}
        reference_data: {category: reference_value}
        categories: list of category names
        x_labels: labels for x-axis
        chart_path: output file path
        title: chart title
        xlabel: x-axis label
        ylabel: y-axis label
        value_label: label for value annotations
        ratio_label: label for colorbar
        cmap: matplotlib colormap name
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    _setup_chinese_font()

    if not value_data:
        return ""

    n_categories = len(categories)
    n_periods = len(x_labels)

    # Build ratio matrix
    ratio_matrix = np.zeros((n_categories, n_periods))
    for i, cat in enumerate(categories):
        values = value_data.get(cat, [0] * n_periods)
        ref = reference_data.get(cat, 1)
        for j in range(n_periods):
            if j < len(values):
                ratio = values[j] / ref if ref > 0 else 999
                ratio_matrix[i, j] = min(ratio, 5)

    fig, ax = plt.subplots(figsize=(12, 6))

    im = ax.imshow(ratio_matrix, cmap=cmap, aspect='auto', vmin=0, vmax=3)

    ax.set_xticks(range(n_periods))
    ax.set_xticklabels(x_labels, rotation=45 if n_periods > 6 else 0)
    ax.set_yticks(range(n_categories))
    ax.set_yticklabels([c[:10] for c in categories], fontsize=9)

    # Add value annotations
    for i in range(n_categories):
        for j in range(n_periods):
            values = value_data.get(categories[i], [0] * n_periods)
            val = values[j] if j < len(values) else 0
            color = 'white' if ratio_matrix[i, j] < 1.5 else 'black'
            ax.text(j, i, f'{val:.0f}', ha='center', va='center',
                    fontsize=9, fontweight='bold', color=color)

    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label(ratio_label)

    plt.tight_layout()
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    return chart_path


# ── Tool spec and handler ──

VISUALIZATION_TOOL_SPEC = {
    "name": "visualization",
    "description": (
        "Generate visual charts from optimization results. "
        "Chart types:\n"
        "- variables: Bar chart of variable values\n"
        "- sensitivity: Sensitivity analysis line chart\n"
        "- heatmap: Constraint tightness heatmap\n"
        "- pareto: Pareto front visualization\n"
        "- trend: Multi-subplot trend chart with optional threshold lines\n"
        "- stacked_bar: Stacked bar chart for category comparisons\n"
        "- scatter_gantt: Scatter-based timeline/Gantt chart\n"
        "- pie: Pie/distribution chart\n"
        "- ratio_heatmap: Heatmap showing ratios to reference values\n"
        "Output: PNG image file path."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "chart_type": {
                "type": "string",
                "enum": [
                    "variables", "sensitivity", "heatmap", "pareto",
                    "trend", "stacked_bar", "scatter_gantt",
                    "pie", "ratio_heatmap", "all"
                ],
                "description": "Chart type to generate",
                "default": "all",
            },
            "variables": {
                "type": "object",
                "description": 'Variable values for bar chart, e.g. {"x": 10.0, "y": 0.0}',
            },
            "objective": {
                "type": "number",
                "description": "Objective function value (for variables chart)",
            },
            "param_data": {
                "type": "array",
                "description": 'Sensitivity data: [{"delta": 0, "objective": 30}, ...]',
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
            "series_data": {
                "type": "object",
                "description": 'Time series data for trend chart: {"series1": [100, 90, 80], ...}',
            },
            "category_data": {
                "type": "object",
                "description": 'Category data for stacked_bar/pie: {"cat1": [10, 20], ...} or {"cat1": 100, ...}',
            },
            "event_data": {
                "type": "object",
                "description": 'Event data for scatter_gantt: {"item1": [0, 100, 0], ...}',
            },
            "value_data": {
                "type": "object",
                "description": 'Value data for ratio_heatmap: {"item1": [100, 90, 80], ...}',
            },
            "reference_data": {
                "type": "object",
                "description": 'Reference values for ratio_heatmap: {"item1": 50, ...}',
            },
            "categories": {
                "type": "array",
                "description": 'List of category/series names',
                "items": {"type": "string"},
            },
            "x_labels": {
                "type": "array",
                "description": 'Labels for x-axis (periods, weeks, etc.)',
                "items": {"type": "string"},
            },
            "title": {
                "type": "string",
                "description": "Chart title",
            },
            "xlabel": {
                "type": "string",
                "description": "X-axis label",
            },
            "ylabel": {
                "type": "string",
                "description": "Y-axis label",
            },
            "threshold_lines": {
                "type": "object",
                "description": 'Threshold lines for trend chart: {"safety": 50, ...}',
            },
            "fill_threshold": {
                "type": "number",
                "description": "Fill area below this threshold (for trend chart)",
            },
            "colors_list": {
                "type": "array",
                "description": 'Custom colors for pie chart',
                "items": {"type": "string"},
            },
            "filename_prefix": {
                "type": "string",
                "description": "Optional prefix for output filenames",
            },
        },
    },
}


async def visualization_handler(args: dict[str, Any], session=None) -> tuple[str, bool]:
    """Handler for visualization tool."""
    chart_type = args.get("chart_type", "all")
    variables = args.get("variables", {})
    objective = args.get("objective", 0)
    param_data = args.get("param_data", [])
    var_name = args.get("var_name", "x")
    gap_data = args.get("gap_data", [])
    constraints = args.get("constraints", {})
    pareto_data = args.get("pareto_data", [])
    series_data = args.get("series_data", {})
    category_data = args.get("category_data", {})
    event_data = args.get("event_data", {})
    value_data = args.get("value_data", {})
    reference_data = args.get("reference_data", {})
    categories = args.get("categories", [])
    x_labels = args.get("x_labels", [])
    title = args.get("title", "")
    xlabel = args.get("xlabel", "")
    ylabel = args.get("ylabel", "")
    threshold_lines = args.get("threshold_lines", {})
    fill_threshold = args.get("fill_threshold")
    colors_list = args.get("colors_list")
    filename_prefix = args.get("filename_prefix", "")

    if chart_type in ("variables", "all") and not variables:
        return "No variable data provided for visualization. Pass `variables` dict, e.g. {\"x\": 10, \"y\": 0}.", True

    if variables:
        bad = {k: v for k, v in variables.items() if not isinstance(v, (int, float))}
        if bad:
            return f"Variable values must be numeric. Invalid: {bad}", True

    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return "matplotlib is not installed. Run: uv add matplotlib", True

    workspace = get_workspace_dir(session)
    prefix = filename_prefix.rstrip("_") if filename_prefix else ""
    charts = []

    def _chart_path(base_name: str) -> str:
        name = f"{prefix}_{base_name}" if prefix else base_name
        return str(workspace / suggest_filename(workspace, name, ".png"))

    try:
        # Original chart types (now with customizable labels)
        if chart_type in ("variables", "all") and variables:
            path = _chart_path("variables")
            _generate_variable_chart(variables, objective, path,
                                     title=title, xlabel=xlabel, ylabel=ylabel or "Value")
            record_file(workspace, Path(path).name, file_type="chart",
                        tool="visualization", note="Variable values bar chart")
            charts.append(("Variable Values", path))

        if chart_type in ("sensitivity", "all") and param_data:
            path = _chart_path("sensitivity")
            _generate_sensitivity_chart(param_data, var_name, path,
                                        title=title, xlabel=xlabel, ylabel=ylabel or "Objective Value")
            record_file(workspace, Path(path).name, file_type="chart",
                        tool="visualization", note=f"Sensitivity: {var_name}")
            charts.append(("Sensitivity Analysis", path))

        if chart_type in ("heatmap", "all") and constraints:
            path = _chart_path("constraint_heatmap")
            _generate_constraint_heatmap(constraints, path,
                                         title=title or "Constraint Tightness Heatmap",
                                         xlabel=xlabel, ylabel=ylabel or "Slack")
            record_file(workspace, Path(path).name, file_type="chart",
                        tool="visualization", note="Constraint tightness heatmap")
            charts.append(("Constraint Tightness Heatmap", path))

        if chart_type in ("pareto", "all") and pareto_data:
            path = _chart_path("pareto_front")
            _generate_pareto_front(pareto_data, path,
                                   title=title or "Pareto Front",
                                   xlabel=xlabel or "Objective 1",
                                   ylabel=ylabel or "Objective 2")
            record_file(workspace, Path(path).name, file_type="chart",
                        tool="visualization", note="Pareto front")
            charts.append(("Pareto Front", path))

        if gap_data and chart_type in ("all",):
            path = _chart_path("gap_progress")
            _generate_gap_chart(gap_data, path,
                                title=title or "Solver Progress",
                                xlabel=xlabel or "Time (s)",
                                ylabel=ylabel or "Gap")
            record_file(workspace, Path(path).name, file_type="chart",
                        tool="visualization", note="Solver gap convergence")
            charts.append(("Solver Progress", path))

        # New generic chart types
        if chart_type in ("trend", "all") and series_data:
            path = _chart_path("trend")
            cats = categories or list(series_data.keys())
            labels = x_labels or [str(i+1) for i in range(len(next(iter(series_data.values()), [])))]
            _generate_trend_chart(
                series_data, labels, path,
                title=title or "Trend Analysis",
                xlabel=xlabel or "Period", ylabel=ylabel or "Value",
                threshold_lines=threshold_lines or None,
                fill_threshold=fill_threshold
            )
            record_file(workspace, Path(path).name, file_type="chart",
                        tool="visualization", note="Trend analysis chart")
            charts.append(("Trend Analysis", path))

        if chart_type in ("stacked_bar", "all") and category_data:
            path = _chart_path("stacked_bar")
            cats = categories or list(category_data.keys())
            labels = x_labels or [f"P{i+1}" for i in range(len(next(iter(category_data.values()), [])))]
            _generate_stacked_bar_chart(
                category_data, cats, labels, path,
                title=title or "Stacked Bar Chart",
                xlabel=xlabel or "Category", ylabel=ylabel or "Value"
            )
            record_file(workspace, Path(path).name, file_type="chart",
                        tool="visualization", note="Stacked bar chart")
            charts.append(("Stacked Bar", path))

        if chart_type in ("scatter_gantt", "all") and event_data:
            path = _chart_path("scatter_gantt")
            cats = categories or list(event_data.keys())
            labels = x_labels or [f"P{i+1}" for i in range(len(next(iter(event_data.values()), [])))]
            _generate_scatter_gantt_chart(
                event_data, cats, labels, path,
                title=title or "Event Timeline",
                xlabel=xlabel or "Period"
            )
            record_file(workspace, Path(path).name, file_type="chart",
                        tool="visualization", note="Scatter Gantt chart")
            charts.append(("Scatter Gantt", path))

        if chart_type in ("pie", "all") and category_data and not any(
            isinstance(v, list) for v in category_data.values()
        ):
            path = _chart_path("pie")
            _generate_pie_chart(
                category_data, path,
                title=title or "Distribution",
                colors_list=colors_list
            )
            record_file(workspace, Path(path).name, file_type="chart",
                        tool="visualization", note="Pie chart")
            charts.append(("Pie Chart", path))

        if chart_type in ("ratio_heatmap", "all") and value_data:
            path = _chart_path("ratio_heatmap")
            cats = categories or list(value_data.keys())
            labels = x_labels or [f"P{i+1}" for i in range(len(next(iter(value_data.values()), [])))]
            _generate_ratio_heatmap(
                value_data, reference_data, cats, labels, path,
                title=title or "Ratio Heatmap",
                xlabel=xlabel or "Period", ylabel=ylabel or "Category",
                value_label=ylabel or "Value", ratio_label="Ratio"
            )
            record_file(workspace, Path(path).name, file_type="chart",
                        tool="visualization", note="Ratio heatmap")
            charts.append(("Ratio Heatmap", path))

        if not charts:
            return "No data provided for visualization", True

        result = "## Visualization Results\n\n"
        for chart_title, path in charts:
            result += f"- **{chart_title}**: `{path}`\n"

        return result, False

    except Exception as e:
        return f"Error generating chart: {e}", True
