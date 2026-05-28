"""Shared output directory helper — ensures all tools in a run write to the same folder."""

import time
from pathlib import Path

_MARKER_NAME = ".current_run"


def get_run_dir() -> Path:
    """Get or create the current run's output directory under outputs/.

    First call in a run creates a new timestamped subdirectory and
    writes a marker file. Subsequent calls by other tools in the same
    run reuse the same directory.

    Returns:
        Absolute path to the run directory, guaranteed to exist.
    """
    outdir = Path(__file__).parent.parent.parent / "outputs"
    marker = outdir / _MARKER_NAME

    if marker.exists():
        run_id = marker.read_text(encoding="utf-8").strip()
        rundir = outdir / run_id
        if rundir.exists():
            return rundir

    ts = time.strftime("%Y%m%d_%H%M%S")
    rundir = outdir / f"run_{ts}"
    rundir.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"run_{ts}", encoding="utf-8")
    return rundir


def clear_run_marker() -> None:
    """Clear the current run marker file.

    Call this at the start of each new user input to ensure
    a fresh output directory is created for the next run.
    """
    outdir = Path(__file__).parent.parent.parent / "outputs"
    marker = outdir / _MARKER_NAME
    if marker.exists():
        marker.unlink()