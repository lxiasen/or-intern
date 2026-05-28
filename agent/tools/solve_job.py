"""solve_job tool for OR-Intern v0.5.

Executes optimization solves using Pyomo + HiGHS (or other solvers).
Supports streaming progress monitoring with real-time gap/bound/nodes parsing.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300
MAX_TIMEOUT = 36000


@dataclass
class SolveProgress:
    """Real-time solve progress snapshot."""
    elapsed_s: float = 0.0
    nodes: int = 0
    iterations: int = 0
    best_bound: float | None = None
    best_sol: float | None = None
    gap_pct: float | None = None
    status: str = "running"
    raw_line: str = ""


@dataclass
class SolveResult:
    """Final solve result with progress history."""
    status: str = "UNKNOWN"
    objective: float | None = None
    variables: dict[str, float] = field(default_factory=dict)
    gap: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    elapsed_s: float = 0.0
    solver_time_s: float | None = None
    nodes: int | None = None
    iterations: int | None = None
    progress_snapshots: list[SolveProgress] = field(default_factory=list)
    solver_log_tail: str = ""


# ── HiGHS / SCIP / GLKP log parsers ──

_HIGHS_MIP_RE = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+"
    r"([\d.eE+\-]+|inf)\s+([\d.eE+\-]+|inf)\s+([\d.eE+\-]+|inf)"
)
_HIGHS_LP_ITER_RE = re.compile(
    r"^\s*(\d+)\s+([\d.eE+\-]+)"
)
_HIGHS_OBJ_RE = re.compile(r"Objective value\s*:\s*([\d.eE+\-]+)")
_HIGHS_STATUS_RE = re.compile(r"Model\s*status\s*:\s*(\S.+\S)")
_HIGHS_ITER_RE = re.compile(r"(?:Simplex|IPM)\s+iterations:\s*(\d+)")
_HIGHS_TIME_RE = re.compile(r"Timing\s+([\d.]+)\s*\(total\)")
_HIGHS_NODES_RE = re.compile(r"Nodes\s+(\d+)")
_HIGHS_MIP_STATUS_RE = re.compile(r"Status\s+(Optimal|Feasible|Infeasible|Unbounded|Time Limit|Node Limit)")
_HIGHS_MIP_OBJ_RE = re.compile(r"Objective value\s*:\s*([\d.eE+\-]+)")
_HIGHS_MIP_BOUND_RE = re.compile(r"(?:Primal|Dual) bound\s*:\s*([\d.eE+\-]+)")
_HIGHS_MIP_GAP_RE = re.compile(r"Gap\s*([\d.]+)%")

_SCIP_STATUS_RE = re.compile(r"^SCIP Status\s*:\s*(.*)")
_SCIP_OBJ_RE = re.compile(r"^Primal Bound\s*:\s*([\d.eE+\-]+)")
_SCIP_BOUND_RE = re.compile(r"^Dual Bound\s*:\s*([\d.eE+\-]+)")
_SCIP_GAP_RE = re.compile(r"Gap\s*:\s*([\d.eE+\-]+)\s*%")
_SCIP_NODES_RE = re.compile(r"^Solving Nodes\s*:\s*(\d+)")
_SCIP_ITER_RE = re.compile(r"^Total Iterations\s*:\s*(\d+)")
_SCIP_TIME_RE = re.compile(r"^Solving Time\s*:\s*([\d.]+)")

_GENERIC_STATUS_RE = re.compile(r"(?:Status|STATUS)\s*:\s*(\S+)")
_GENERIC_OBJ_RE = re.compile(r"(?:Objective|OBJECTIVE)\s*:\s*([\d.eE+\-]+)")


def _parse_hipghs_progress(line: str, t0: float) -> SolveProgress | None:
    """Parse a single HiGHS log line into a progress snapshot."""
    p = SolveProgress(elapsed_s=time.monotonic() - t0, raw_line=line)

    m = _HIGHS_MIP_RE.match(line)
    if m:
        p.nodes = int(m.group(1))
        p.iterations = int(m.group(2))
        try:
            p.best_bound = float(m.group(5))
        except ValueError:
            pass
        try:
            p.best_sol = float(m.group(6))
        except ValueError:
            pass
        try:
            p.gap_pct = float(m.group(7).replace("%", ""))
        except ValueError:
            pass
        return p

    m = _HIGHS_LP_ITER_RE.match(line)
    if m:
        p.iterations = int(m.group(1))
        try:
            p.best_bound = float(m.group(2))
        except ValueError:
            pass
        return p

    return None


def _parse_scip_progress(line: str, t0: float) -> SolveProgress | None:
    """Parse a single SCIP log line."""
    m = re.match(
        r"\|\s*\d+\s*\|\s*\d+\s*\|\s*[\d.]+\s*\|\s*"
        r"([\d.eE+\-]+)\s*\|\s*([\d.eE+\-]+)\s*\|\s*([\d.]+)%",
        line,
    )
    if m:
        p = SolveProgress(elapsed_s=time.monotonic() - t0, raw_line=line)
        try:
            p.best_bound = float(m.group(1))
            p.best_sol = float(m.group(2))
            p.gap_pct = float(m.group(3))
        except ValueError:
            pass
        return p
    return None


def _parse_generic_progress(line: str, t0: float) -> SolveProgress | None:
    """Generic progress parser (GLPK, CBC, etc.)."""
    m = _GENERIC_OBJ_RE.search(line)
    if m:
        p = SolveProgress(elapsed_s=time.monotonic() - t0, raw_line=line)
        try:
            p.best_bound = float(m.group(1))
        except ValueError:
            pass
        return p
    return None


def _parse_progress_line(line: str, solver_name: str, t0: float) -> SolveProgress | None:
    """Dispatch to the right parser based on solver name."""
    name = solver_name.lower()
    if "highs" in name:
        return _parse_hipghs_progress(line, t0)
    if "scip" in name:
        return _parse_scip_progress(line, t0)
    return _parse_generic_progress(line, t0)


def _parse_solution_from_output(output: str) -> SolveResult:
    """Parse OR_INTERN_SOLUTION markers from solve output."""
    result = SolveResult()

    if "OR_INTERN_SOLUTION_START" in output:
        section = output.split("OR_INTERN_SOLUTION_START")[1]
        section = section.split("OR_INTERN_SOLUTION_END")[0]
    else:
        section = output

    for line in section.split("\n"):
        line = line.strip()
        if re.match(r"(?:STATUS|Status):", line, re.IGNORECASE):
            result.status = line.split(":", 1)[1].strip().upper()
        elif re.match(r"(?:OBJECTIVE|Objective):", line, re.IGNORECASE):
            try:
                result.objective = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif re.match(r"(?:GAP|Gap):", line, re.IGNORECASE):
            try:
                result.gap = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif re.match(r"(?:LOWER_BOUND|Lower_bound):", line, re.IGNORECASE):
            try:
                result.lower_bound = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif re.match(r"(?:UPPER_BOUND|Upper_bound):", line, re.IGNORECASE):
            try:
                result.upper_bound = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif re.match(r"(?:NODES|Nodes):", line, re.IGNORECASE):
            try:
                result.nodes = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif re.match(r"(?:ITERATIONS|Iterations):", line, re.IGNORECASE):
            try:
                result.iterations = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif re.match(r"(?:SOLVER_TIME|Solver_time):", line, re.IGNORECASE):
            try:
                result.solver_time_s = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif "=" in line and not any(
            kw in line.lower()
            for kw in ["status", "objective", "solve", "termination", "gap", "lower", "upper", "node", "iter", "time"]
        ):
            parts = line.split("=", 1)
            name = parts[0].strip()
            try:
                val = float(parts[1].strip())
                result.variables[name] = val
            except ValueError:
                pass

    return result


def _format_progress(snap: SolveProgress) -> str:
    """Format a progress snapshot for display."""
    parts = [f"⏱ {snap.elapsed_s:.1f}s"]
    if snap.nodes > 0:
        parts.append(f"🌳 {snap.nodes} nodes")
    if snap.iterations > 0:
        parts.append(f"🔄 {snap.iterations} iter")
    if snap.best_bound is not None:
        parts.append(f"bound={snap.best_bound:.4g}")
    if snap.best_sol is not None and snap.best_sol < 1e15:
        parts.append(f"best={snap.best_sol:.4g}")
    if snap.gap_pct is not None:
        parts.append(f"gap={snap.gap_pct:.2f}%")
    return " | ".join(parts)


def _format_result(result: SolveResult, solver_name: str) -> str:
    """Format final solve result as Markdown."""
    out = f"## Solve Results\n\n"
    out += f"**Status**: {result.status}\n"
    out += f"**Solver**: {solver_name}\n"
    out += f"**Time**: {result.elapsed_s:.1f}s\n"

    if result.objective is not None:
        out += f"**Objective value**: {result.objective}\n"
    if result.gap is not None:
        out += f"**Gap**: {result.gap:.6g}\n"
    if result.lower_bound is not None:
        out += f"**Lower bound**: {result.lower_bound:.6g}\n"
    if result.upper_bound is not None:
        out += f"**Upper bound**: {result.upper_bound:.6g}\n"
    if result.nodes is not None:
        out += f"**B&B nodes**: {result.nodes}\n"
    if result.iterations is not None:
        out += f"**Iterations**: {result.iterations}\n"
    if result.solver_time_s is not None:
        out += f"**Solver time**: {result.solver_time_s:.2f}s\n"

    if result.variables:
        out += "\n**Variable values**:\n"
        for name, val in sorted(result.variables.items()):
            out += f"  - {name} = {val}\n"

    if result.progress_snapshots:
        n = len(result.progress_snapshots)
        out += f"\n**Progress** ({n} snapshots):\n```\n"
        sampled = result.progress_snapshots[:: max(1, n // 10)][:10]
        for snap in sampled:
            out += _format_progress(snap) + "\n"
        if n > 10:
            out += f"... ({n} total snapshots)\n"
        out += "```\n"

    if result.solver_log_tail:
        out += f"\n**Solver log** (tail):\n```\n{result.solver_log_tail}\n```\n"

    return result, out


# ── Tool spec ──

SOLVE_JOB_TOOL_SPEC = {
    "name": "solve_job",
    "description": (
        "Execute an optimization solve using Pyomo and a specified solver. "
        "Supports real-time progress monitoring (gap, bound, nodes). "
        "Operations: 'run' (execute solve), 'status' (check solver availability). "
        "Returns solution status, objective, variables, gap, and progress history."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["run", "status"],
                "description": "Operation: 'run' to solve, 'status' to check solver availability",
                "default": "run",
            },
            "model_path": {
                "type": "string",
                "description": "Path to the Pyomo model Python file",
            },
            "solver": {
                "type": "string",
                "description": "Solver to use (default: highs)",
                "default": "highs",
            },
            "timeout": {
                "type": "integer",
                "description": f"Maximum solve time in seconds (default: {DEFAULT_TIMEOUT})",
                "default": DEFAULT_TIMEOUT,
            },
            "stream_progress": {
                "type": "boolean",
                "description": "Enable real-time progress reporting (default: true)",
                "default": True,
            },
        },
    },
}


async def _stream_output(
    stream: asyncio.StreamReader,
    solver_name: str,
    t0: float,
    progress_callback=None,
) -> tuple[list[str], list[SolveProgress]]:
    """Read stream line by line, parse progress, optionally call back."""
    lines: list[str] = []
    snapshots: list[SolveProgress] = []
    last_report_t = 0.0

    while True:
        raw = await stream.readline()
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        lines.append(line)

        snap = _parse_progress_line(line, solver_name, t0)
        if snap:
            snapshots.append(snap)
            now = time.monotonic()
            if progress_callback and now - last_report_t >= 1.0:
                last_report_t = now
                try:
                    await progress_callback(snap)
                except Exception:
                    pass

    return lines, snapshots


async def solve_job_handler(args: dict[str, Any], session=None) -> tuple[str, bool]:
    """Handler for solve_job tool with streaming progress."""
    operation = args.get("operation", "run")

    if operation == "status":
        return await _check_solver_status()

    model_path_str = args.get("model_path", "")
    solver_name = args.get("solver", "highs")
    timeout = args.get("timeout", DEFAULT_TIMEOUT)
    stream_progress = args.get("stream_progress", True)

    if not model_path_str:
        return "Error: No model path provided", True

    model_path = Path(model_path_str)
    if not model_path.exists():
        return f"Error: Model file not found: {model_path}", True

    import sys
    python_exe = sys.executable
    t0 = time.monotonic()

    try:
        process = await asyncio.create_subprocess_exec(
            python_exe,
            str(model_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(model_path.parent),
        )

        progress_callback = None
        if stream_progress and session is not None:
            async def progress_callback(snap: SolveProgress):
                from agent.core.session import Event
                await session.send_event(Event(
                    event_type="solve_progress",
                    data={
                        "tool": "solve_job",
                        "elapsed_s": snap.elapsed_s,
                        "nodes": snap.nodes,
                        "iterations": snap.iterations,
                        "best_bound": snap.best_bound,
                        "best_sol": snap.best_sol,
                        "gap_pct": snap.gap_pct,
                        "formatted": _format_progress(snap),
                    },
                ))

        read_timeout = min(timeout, MAX_TIMEOUT)

        stdout_lines, stdout_snapshots = [], []
        stderr_lines, stderr_snapshots = [], []

        async def _read_stdout():
            nonlocal stdout_lines, stdout_snapshots
            stdout_lines, stdout_snapshots = await _stream_output(
                process.stdout, solver_name, t0, progress_callback
            )

        async def _read_stderr():
            nonlocal stderr_lines, stderr_snapshots
            stderr_lines, stderr_snapshots = await _stream_output(
                process.stderr, solver_name, t0, None
            )

        try:
            await asyncio.wait_for(
                asyncio.gather(_read_stdout(), _read_stderr()),
                timeout=read_timeout,
            )
            await process.wait()
        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            elapsed = time.monotonic() - t0
            return (
                f"## Solve Timed Out\n\n"
                f"**Time limit**: {timeout}s\n"
                f"**Elapsed**: {elapsed:.1f}s\n"
                f"Try increasing the timeout or simplifying the model.",
                True,
            )

        elapsed = time.monotonic() - t0
        stdout_str = "\n".join(stdout_lines)
        stderr_str = "\n".join(stderr_lines)

        if process.returncode != 0:
            return (
                f"## Solve Failed (exit code {process.returncode})\n\n"
                f"**Time**: {elapsed:.1f}s\n\n"
                f"**Error output**:\n```\n{stderr_str[-2000:]}\n```\n\n"
                f"**Stdout tail**:\n```\n{stdout_str[-1000:]}\n```",
                True,
            )

        result = _parse_solution_from_output(stdout_str)
        result.elapsed_s = elapsed
        result.solver_log_tail = "\n".join(stderr_lines[-5:])
        result.progress_snapshots = stdout_snapshots + stderr_snapshots

        if result.status == "UNKNOWN":
            return (
                f"## Solve Completed (status unclear)\n\n"
                f"**Time**: {elapsed:.1f}s\n"
                f"**Exit code**: {process.returncode}\n\n"
                f"**Output**:\n```\n{stdout_str[-2000:]}\n```",
                False,
            )

        _, formatted = _format_result(result, solver_name)
        return formatted, False

    except Exception as e:
        logger.error(f"solve_job failed: {e}")
        return f"Error: {e}", True


async def _check_solver_status() -> tuple[str, bool]:
    """Check availability of known solvers."""
    solvers = []
    for name in ["highs", "scip", "glpk", "gurobi", "cplex", "cbc", "ipopt"]:
        try:
            from pyomo.environ import SolverFactory
            s = SolverFactory(name)
            if s.available():
                solvers.append(f"✅ {name}")
            else:
                solvers.append(f"❌ {name} (not available)")
        except Exception:
            solvers.append(f"❌ {name} (not found)")
    return "## Solver Status\n\n" + "\n".join(solvers), False
