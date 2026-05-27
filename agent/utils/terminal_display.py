"""OR-Intern terminal display utilities.

Stub module — simplified from ML-Intern.
"""


def format_plan_tool_output(todos: list) -> str:
    """Format plan tool output for display."""
    if not todos:
        return "No items in plan."

    lines = ["Plan:"]
    for i, todo in enumerate(todos, 1):
        status = "✓" if todo.get("completed") else "○"
        text = todo.get("text", str(todo))
        lines.append(f"  [{status}] {text}")
    return "\n".join(lines)
