"""OR-Intern v0.5 terminal display utilities.

Rich TUI formatting for optimization workflows, solver progress,
phase tracking, and result presentation.
"""

import time
from typing import Any

BANNER = r"""
  ╔══════════════════════════════════════╗
  ║          OR-Intern  v0.5.0           ║
  ║   Operations Research AI Agent       ║
  ╚══════════════════════════════════════╝
"""

PHASES = [
    ("1", "MODEL", "model_builder"),
    ("2", "SOLVE", "solve_job"),
    ("3", "VALIDATE", "validate_solution"),
    ("4", "ANALYZE", "sensitivity_analysis"),
    ("5", "VISUALIZE", "visualization"),
    ("6", "REPORT", "report_generator"),
]


def format_phase_tracker(current_phase: int, completed_phases: set[int] | None = None) -> str:
    """Render the 6-phase workflow progress bar."""
    completed = completed_phases or set()
    lines = ["  ┌─ OR Pipeline ─────────────────────┐"]
    for num, name, _ in PHASES:
        n = int(num)
        if n in completed:
            marker = "✅"
        elif n == current_phase:
            marker = "🔄"
        else:
            marker = "  "
        lines.append(f"  │ {marker} Phase {num}: {name:<12}       │")
    lines.append("  └─────────────────────────────────────┘")
    return "\n".join(lines)


def format_solve_progress(
    elapsed_s: float,
    nodes: int = 0,
    iterations: int = 0,
    best_bound: float | None = None,
    best_sol: float | None = None,
    gap_pct: float | None = None,
) -> str:
    """Format real-time solver progress as a one-liner."""
    parts = [f"⏱ {elapsed_s:.1f}s"]
    if nodes > 0:
        parts.append(f"🌳 {nodes}")
    if iterations > 0:
        parts.append(f"🔄 {iterations}")
    if best_bound is not None:
        parts.append(f"bound={best_bound:.4g}")
    if best_sol is not None and best_sol < 1e15:
        parts.append(f"best={best_sol:.4g}")
    if gap_pct is not None:
        gap_str = f"{gap_pct:.2f}%"
        if gap_pct < 0.1:
            gap_str = f"✅ {gap_str}"
        elif gap_pct > 5:
            gap_str = f"⚠️ {gap_str}"
        parts.append(f"gap={gap_str}")
    return " │ ".join(parts)


def format_plan_tool_output(todos: list) -> str:
    """Format plan tool output for display."""
    if not todos:
        return "No items in plan."
    lines = ["Plan:"]
    for i, todo in enumerate(todos, 1):
        if isinstance(todo, dict):
            status = todo.get("status", "pending")
            text = todo.get("content", str(todo))
            if status == "completed":
                marker = "✅"
            elif status == "in_progress":
                marker = "🔄"
            else:
                marker = "○"
        else:
            marker = "○"
            text = str(todo)
        lines.append(f"  {marker} {text}")
    return "\n".join(lines)


def format_solve_result_summary(
    status: str,
    objective: float | None,
    elapsed_s: float,
    gap: float | None = None,
    solver: str = "",
) -> str:
    """Format a compact solve result summary."""
    lines = []
    if status.upper() in ("OPTIMAL",):
        lines.append(f"  ✅ {status}")
    elif status.upper() in ("FEASIBLE",):
        lines.append(f"  ⚠️ {status}")
    else:
        lines.append(f"  ❌ {status}")

    if objective is not None:
        lines.append(f"  Objective: {objective:.6g}")
    if gap is not None:
        lines.append(f"  Gap: {gap:.6g}")
    lines.append(f"  Time: {elapsed_s:.1f}s")
    if solver:
        lines.append(f"  Solver: {solver}")
    return "\n".join(lines)


def format_tool_call(tool_name: str, args: dict | None = None) -> str:
    """Format a tool call for display."""
    if args:
        key_args = {k: v for k, v in args.items() if k not in ("model_path",)}
        if key_args:
            args_str = ", ".join(f"{k}={v}" for k, v in key_args.items() if v is not None)
            return f"  ⏳ {tool_name}({args_str})"
    return f"  ⏳ {tool_name}..."


def format_tool_result(tool_name: str, output: str, is_error: bool) -> str:
    """Format tool result for compact display."""
    if is_error:
        lines = output.strip().split("\n")
        if len(lines) <= 10:
            preview = "\n     ".join(lines)
            return f"\n  ❌ {tool_name}\n     {preview}"
        preview = "\n     ".join(lines[:10])
        return f"\n  ❌ {tool_name} ({len(lines)} lines)\n     {preview}"
    lines = output.strip().split("\n")
    if len(lines) <= 10:
        preview = "\n     ".join(lines)
        return f"\n  ✅ {tool_name}\n     {preview}"
    # For longer outputs, show first 10 lines and count
    preview = "\n     ".join(lines[:10])
    return f"\n  ✅ {tool_name} ({len(lines)} lines)\n     {preview}"
