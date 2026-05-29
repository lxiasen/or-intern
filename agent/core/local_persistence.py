"""Local session persistence for OR-Intern.

Provides file-based session storage for the CLI, saving optimization
trajectories as JSON files that can be replayed or shared.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LocalSessionStore:
    """File-based session store for local CLI usage."""

    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            base_dir = Path.home() / ".or-intern" / "sessions"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, session_id: str) -> Path:
        """Get directory for a specific session."""
        d = self.base_dir / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_trajectory(self, session_id: str, trajectory: dict[str, Any]) -> Path:
        """Save an optimization trajectory to a JSON file.

        Args:
            session_id: Unique session identifier
            trajectory: Dict containing:
                - problem_description: str
                - model_code: str (Pyomo code)
                - solver: str
                - solution: dict (variable values)
                - objective: float
                - status: str
                - messages: list (conversation history)
                - timestamps: dict (start, end, etc.)

        Returns:
            Path to saved trajectory file
        """
        session_dir = self._session_dir(session_id)

        # Add metadata
        trajectory["session_id"] = session_id
        trajectory["saved_at"] = datetime.now().isoformat()
        trajectory["schema_version"] = 1

        # Save main trajectory
        filepath = session_dir / "trajectory.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(trajectory, f, indent=2, ensure_ascii=False, default=str)

        logger.info("Saved trajectory to %s", filepath)
        return filepath

    def load_trajectory(self, session_id: str) -> dict[str, Any] | None:
        """Load an optimization trajectory.

        Args:
            session_id: Session identifier

        Returns:
            Trajectory dict or None if not found
        """
        filepath = self._session_dir(session_id) / "trajectory.json"
        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to load trajectory %s: %s", session_id, e)
            return None

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List saved sessions with metadata.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session summaries
        """
        sessions = []
        for session_dir in sorted(self.base_dir.iterdir(), reverse=True):
            if not session_dir.is_dir():
                continue
            trajectory_file = session_dir / "trajectory.json"
            if trajectory_file.exists():
                try:
                    with open(trajectory_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    sessions.append({
                        "session_id": data.get("session_id", session_dir.name),
                        "problem_description": data.get("problem_description", "")[:100],
                        "status": data.get("status", "unknown"),
                        "objective": data.get("objective"),
                        "saved_at": data.get("saved_at", ""),
                    })
                except (json.JSONDecodeError, IOError):
                    continue
            if len(sessions) >= limit:
                break
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a saved session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        session_dir = self._session_dir(session_id)
        if not session_dir.exists():
            return False

        # Remove trajectory file
        trajectory_file = session_dir / "trajectory.json"
        if trajectory_file.exists():
            trajectory_file.unlink()

        # Remove model file if exists
        model_file = session_dir / "model.py"
        if model_file.exists():
            model_file.unlink()

        # Remove directory if empty
        try:
            session_dir.rmdir()
        except OSError:
            pass

        return True

    def save_model(self, session_id: str, model_code: str) -> Path:
        """Save model code to session directory.

        Args:
            session_id: Session identifier
            model_code: Pyomo model code

        Returns:
            Path to saved model file
        """
        session_dir = self._session_dir(session_id)
        filepath = session_dir / "model.py"
        filepath.write_text(model_code, encoding="utf-8")
        return filepath

    def save_report(self, session_id: str, report: str) -> Path:
        """Save report to session directory.

        Args:
            session_id: Session identifier
            report: Report content (Markdown)

        Returns:
            Path to saved report file
        """
        session_dir = self._session_dir(session_id)
        filepath = session_dir / "report.md"
        filepath.write_text(report, encoding="utf-8")
        return filepath


def format_trajectory_summary(trajectory: dict[str, Any]) -> str:
    """Format a trajectory summary for display.

    Args:
        trajectory: Trajectory dict

    Returns:
        Formatted summary string
    """
    lines = [
        "## Optimization Trajectory",
        "",
        f"**Session**: {trajectory.get('session_id', 'N/A')}",
        f"**Saved**: {trajectory.get('saved_at', 'N/A')}",
        "",
        "### Problem",
        trajectory.get("problem_description", "N/A"),
        "",
        "### Solution",
        f"- **Status**: {trajectory.get('status', 'N/A')}",
        f"- **Objective**: {trajectory.get('objective', 'N/A')}",
        f"- **Solver**: {trajectory.get('solver', 'N/A')}",
    ]

    variables = trajectory.get("variables", {})
    if variables:
        lines.append("- **Variables**:")
        for name, val in sorted(variables.items()):
            lines.append(f"  - {name} = {val}")

    return "\n".join(lines)


def create_trajectory_from_session(
    problem_description: str,
    model_code: str = "",
    solver: str = "",
    solution: dict | None = None,
    objective: float | None = None,
    status: str = "",
    messages: list | None = None,
) -> dict[str, Any]:
    """Create a trajectory dict from session data.

    Args:
        problem_description: Original problem description
        model_code: Generated Pyomo model code
        solver: Solver used
        solution: Variable values
        objective: Objective function value
        status: Solution status
        messages: Conversation messages

    Returns:
        Trajectory dict ready for saving
    """
    return {
        "problem_description": problem_description,
        "model_code": model_code,
        "solver": solver,
        "variables": solution or {},
        "objective": objective,
        "status": status,
        "messages": messages or [],
        "timestamps": {
            "start": datetime.now().isoformat(),
        },
    }
