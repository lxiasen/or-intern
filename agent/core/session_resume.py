"""Session resume for OR-Intern.

Restores a conversation from a previously saved session trajectory JSON
file so the user can continue where they left off.
"""

import json
import logging
from pathlib import Path
from typing import Any

from litellm import Message

logger = logging.getLogger(__name__)


def _load_trajectory(path: Path) -> dict:
    """Load and validate a session trajectory JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Session log not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if "messages" not in data and "events" not in data:
        raise ValueError(
            "Invalid session log: missing 'messages' and 'events' keys"
        )
    return data


def _rebuild_messages(messages_data: list[dict]) -> list[Message]:
    """Convert raw message dicts back into litellm Message objects."""
    result: list[Message] = []
    for raw in messages_data:
        role = raw.get("role", "assistant")
        content = raw.get("content", "")
        kwargs: dict[str, Any] = {}

        if role == "assistant" and raw.get("tool_calls"):
            from litellm import ChatCompletionMessageToolCall

            kwargs["tool_calls"] = [
                ChatCompletionMessageToolCall(**tc) if isinstance(tc, dict) else tc
                for tc in raw["tool_calls"]
            ]

        if raw.get("tool_call_id"):
            kwargs["tool_call_id"] = raw["tool_call_id"]

        if raw.get("name"):
            kwargs["name"] = raw["name"]

        try:
            msg = Message(role=role, content=content or "", **kwargs)
            result.append(msg)
        except Exception as e:
            logger.warning("Skipping malformed message (role=%s): %s", role, e)

    return result


def _build_restore_note(trajectory: dict) -> str:
    """Build a short context note summarizing the previous session."""
    parts: list[str] = []

    session_id = trajectory.get("session_id", "unknown")
    model = trajectory.get("model_name", "unknown")
    cost = trajectory.get("total_cost_usd", 0)
    end_time = trajectory.get("session_end_time", "unknown")

    parts.append(
        f"[Session restored from log: session={session_id[:8]}, "
        f"model={model}, previous cost=${cost:.4f}, ended={end_time}]"
    )

    events = trajectory.get("events", [])
    tool_calls = [
        e for e in events if e.get("event_type") == "tool_call"
    ]
    if tool_calls:
        tools_used: list[str] = []
        for tc in tool_calls[-10:]:
            data = tc.get("data", {})
            name = data.get("tool", "?")
            if name not in tools_used:
                tools_used.append(name)
        if tools_used:
            parts.append(
                f"[Recent tools: {', '.join(tools_used)}]"
            )

    try:
        from agent.tools._output_dir import get_workspace_dir, list_workspace_files

        class _FakeSession:
            pass

        fake = _FakeSession()
        fake.session_id = session_id
        ws_dir = get_workspace_dir(fake)
        ws_info = list_workspace_files(ws_dir)
        if ws_info:
            parts.append(f"[Workspace: {ws_dir}]")
            for line in ws_info.split("\n"):
                stripped = line.strip()
                if stripped.startswith("- "):
                    parts.append(f"  {stripped}")
    except Exception:
        pass

    return "\n".join(parts)


def restore_session_from_log(session: Any, path: Path) -> dict[str, Any]:
    """Restore a session's conversation from a saved trajectory log.

    Parameters
    ----------
    session : Session
        Active session to restore into.
    path : Path
        Path to the session trajectory JSON file.

    Returns
    -------
    dict
        Result metadata including restored message count.
    """
    trajectory = _load_trajectory(path)
    messages_data = trajectory.get("messages", [])

    if not messages_data:
        return {
            "restored": False,
            "message_count": 0,
            "note": "No messages found in session log",
        }

    rebuilt = _rebuild_messages(messages_data)

    if not rebuilt:
        return {
            "restored": False,
            "message_count": 0,
            "note": "All messages were malformed during restore",
        }

    from agent.tools.plan_tool import reset_current_plan

    session.current_plan = []
    reset_current_plan()

    session.context_manager.items = rebuilt
    session.context_manager.running_context_usage = 0

    session.logged_events = []
    session._local_save_path = None
    session._last_heartbeat_ts = None
    session.pending_approval = None
    session.auto_approval_estimated_spend_usd = 0.0
    session.reset_cancel()

    try:
        from agent.core.telemetry import reset_session
        reset_session(session)
    except Exception:
        pass

    try:
        from agent.tools._output_dir import get_workspace_dir
        session.workspace_dir = get_workspace_dir(session)
        session.context_manager.workspace_dir = session.workspace_dir
    except Exception:
        pass

    restore_note = _build_restore_note(trajectory)
    session.context_manager.items.append(
        Message(role="user", content=restore_note)
    )

    return {
        "restored": True,
        "message_count": len(rebuilt),
        "source_path": str(path),
        "source_session_id": trajectory.get("session_id", "unknown"),
        "note": restore_note,
    }


def list_saved_sessions(directory: str = "session_logs") -> list[dict[str, Any]]:
    """List available saved session logs for /resume selection.

    Returns a list of dicts with session_id, timestamp, model, and cost.
    """
    log_dir = Path(directory)
    if not log_dir.exists():
        return []

    sessions: list[dict[str, Any]] = []
    for f in sorted(log_dir.glob("session_*.json"), reverse=True):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            sessions.append({
                "path": str(f),
                "session_id": data.get("session_id", "unknown"),
                "model": data.get("model_name", "unknown"),
                "end_time": data.get("session_end_time", "unknown"),
                "cost_usd": data.get("total_cost_usd", 0),
                "message_count": len(data.get("messages", [])),
            })
        except Exception as e:
            logger.debug("Skipping invalid session log %s: %s", f, e)

    return sessions
