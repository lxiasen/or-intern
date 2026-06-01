"""OR-Intern CLI entry point.

Simplified from ML-Intern — interactive and headless modes.
"""

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

# Load .env from project root (or-intern/)
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.core.session import OpType


# ── Submission types (mirrors ML-Intern main.py) ──

@dataclass
class Operation:
    """Operation to be executed by the agent."""
    op_type: Any
    data: Optional[dict] = None


@dataclass
class Submission:
    """Submission to the agent loop."""
    id: str
    operation: Operation


# ── Helper: Submit user input ──

async def submit_user_input(submission_queue, text, submission_id_counter):
    """Submit a user input to the agent loop."""
    submission_id_counter[0] += 1
    sub = Submission(
        id=f"sub_{submission_id_counter[0]}",
        operation=Operation(
            op_type=OpType.USER_INPUT,
            data={"text": text},
        ),
    )
    await submission_queue.put(sub)


def setup_logging(debug=False):
    """Configure logging for OR-Intern."""
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(level=level, format="%(name)s - %(levelname)s - %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)


def _safe_print(text: str, end: str = ""):
    """Print text safely handling Unicode encoding issues on Windows."""
    try:
        print(text, end=end, flush=True)
    except UnicodeEncodeError:
        safe = text.encode("ascii", errors="replace").decode("ascii")
        print(safe, end=end, flush=True)


async def interactive_main(config, max_iterations=None):
    """Run OR-Intern in interactive mode."""
    from rich.console import Console
    from rich.panel import Panel
    from agent.core.agent_loop import submission_loop
    from agent.core.tools import ToolRouter, create_builtin_tools
    from agent.utils.terminal_display import BANNER, format_tool_call, format_tool_result

    console = Console()

    # Banner
    console.print(BANNER, style="bold green")
    console.print(f"  [dim]Model: {config.current_model.name}[/]")
    console.print()
    console.print("  [dim]Enter your optimization problem and press Enter to start[/]")
    console.print("  [dim]Commands: /help, /model, /exit[/]")
    console.print()

    # Create tool router
    tool_router = ToolRouter()
    for tool in create_builtin_tools():
        tool_router.register(tool)

    # Create queues
    submission_queue = asyncio.Queue()
    event_queue = asyncio.Queue()

    # Session holder (so we can access session for /model commands etc.)
    session_holder = [None]

    # Start agent loop (creates Session internally)
    agent_task = asyncio.create_task(
        submission_loop(
            submission_queue,
            event_queue,
            config=config,
            tool_router=tool_router,
            session_holder=session_holder,
            local_mode=True,
            stream=True,
        )
    )

    submission_id = [0]

    try:
        while True:
            try:
                try:
                    from prompt_toolkit import PromptSession as PS
                    from prompt_toolkit.history import FileHistory
                    ps = PS(history=FileHistory(
                        os.path.join(os.path.expanduser("~"), ".or_intern_history")
                    ))
                    user_input = await ps.prompt_async("You> ")
                except ImportError:
                    user_input = input("You> ")

                if not user_input.strip():
                    continue

                # Commands
                if user_input.startswith("/"):
                    cmd = user_input[1:].strip().lower()
                    if cmd in ("exit", "quit", "q"):
                        console.print("[yellow]Goodbye![/]")
                        break
                    elif cmd == "help":
                        console.print("[bold]Available commands:[/]")
                        console.print("  /help       - Show this help message")
                        console.print("  /model      - Show current model")
                        console.print("  /undo       - Undo last conversation turn")
                        console.print("  /new        - Start new conversation (keep model/config)")
                        console.print("  /compact    - Manually compact context")
                        console.print("  /sessions   - List saved sessions")
                        console.print("  /resume <path> - Resume session from log file")
                        console.print("  /exit       - Exit program")
                        console.print()
                        console.print("[bold]Example problems:[/]")
                        console.print("  • Maximize 5x + 3y subject to 2x + y <= 20, x + 3y <= 30")
                        console.print("  • Solve knapsack problem: capacity=50, weights=[10,20,30], values=[60,100,120]")
                        console.print("  • List all available problem templates")
                        continue
                    elif cmd.startswith("model"):
                        parts = cmd.split(maxsplit=1)
                        if len(parts) >= 2 and parts[1].strip():
                            try:
                                idx = int(parts[1].strip()) - 1
                            except ValueError:
                                console.print("[red]Usage: /model <number> (e.g. /model 2)[/]")
                                continue
                            if idx < 0 or idx >= len(config.models):
                                console.print(f"[red]Invalid index. Choose 1-{len(config.models)}[/]")
                                continue
                            from agent.core.model_switcher import probe_and_switch_model
                            session = session_holder[0]
                            await probe_and_switch_model(idx, config, session, console)
                        else:
                            current_idx = config.active_model_index
                            console.print("[bold]Available models:[/]")
                            for i, m in enumerate(config.models):
                                label = m.display_name or m.name
                                marker = " [dim]<-- current[/dim]" if i == current_idx else ""
                                console.print(f"  [{i+1}] {label} ({m.name}){marker}")
                            console.print("[dim]Use /model <number> to switch[/dim]")
                        continue
                    elif cmd == "undo":
                        undo_sub = Submission(
                            id=f"sub_{submission_id[0] + 1}",
                            operation=Operation(op_type=OpType.UNDO),
                        )
                        submission_id[0] += 1
                        await submission_queue.put(undo_sub)
                        while True:
                            event = await event_queue.get()
                            if event.event_type == "undo_complete":
                                console.print("[green]Last conversation turn undone[/]")
                                break
                            elif event.event_type == "error":
                                console.print(f"[red]Undo failed: {event.data.get('error', '?')}[/]")
                                break
                        continue
                    elif cmd == "new":
                        new_sub = Submission(
                            id=f"sub_{submission_id[0] + 1}",
                            operation=Operation(op_type=OpType.NEW),
                        )
                        submission_id[0] += 1
                        await submission_queue.put(new_sub)
                        while True:
                            event = await event_queue.get()
                            if event.event_type == "new_complete":
                                data = event.data or {}
                                console.print(f"[green]New conversation started (session: {data.get('session_id', '?')[:8]})[/]")
                                break
                            elif event.event_type == "error":
                                console.print(f"[red]Failed to start new conversation: {event.data.get('error', '?')}[/]")
                                break
                        continue
                    elif cmd == "compact":
                        compact_sub = Submission(
                            id=f"sub_{submission_id[0] + 1}",
                            operation=Operation(op_type=OpType.COMPACT),
                        )
                        submission_id[0] += 1
                        await submission_queue.put(compact_sub)
                        console.print("[green]Context compaction request submitted[/]")
                        continue
                    elif cmd == "sessions":
                        from agent.core.session_resume import list_saved_sessions
                        sessions = list_saved_sessions(
                            getattr(config, "session_log_dir", "session_logs")
                        )
                        if not sessions:
                            console.print("[yellow]No saved sessions found[/]")
                        else:
                            console.print(f"[bold]Saved sessions ({len(sessions)}):[/]")
                            for i, s in enumerate(sessions[:20]):
                                console.print(
                                    f"  [{i+1}] {s['session_id'][:8]}  "
                                    f"model={s['model']}  "
                                    f"msgs={s['message_count']}  "
                                    f"cost=${s['cost_usd']:.4f}  "
                                    f"{s['end_time'][:16]}"
                                )
                                console.print(f"       path: {s['path']}")
                            console.print()
                            console.print("[dim]Use /resume <path> to restore a session[/]")
                        continue
                    elif cmd.startswith("resume"):
                        parts = cmd.split(maxsplit=1)
                        if len(parts) < 2 or not parts[1].strip():
                            console.print("[red]Usage: /resume <path> — use /sessions to view available paths[/]")
                            continue
                        resume_path = parts[1].strip()
                        resume_sub = Submission(
                            id=f"sub_{submission_id[0] + 1}",
                            operation=Operation(
                                op_type=OpType.RESUME,
                                data={"path": resume_path},
                            ),
                        )
                        submission_id[0] += 1
                        await submission_queue.put(resume_sub)
                        while True:
                            event = await event_queue.get()
                            if event.event_type == "resume_complete":
                                data = event.data or {}
                                if data.get("restored"):
                                    console.print(
                                        f"[green]Restored {data['message_count']} messages "
                                        f"(from {data.get('source_session_id', '?')[:8]})[/]"
                                    )
                                else:
                                    console.print(f"[yellow]{data.get('note', 'Restore incomplete')}[/]")
                                break
                            elif event.event_type == "error":
                                console.print(f"[red]Restore failed: {event.data.get('error', '?')}[/]")
                                break
                        continue
                    else:
                        console.print(f"[red]Unknown command: {cmd}, type /help for available commands[/]")
                        continue

                # Submit to agent
                await submit_user_input(submission_queue, user_input, submission_id)

                # Display response
                current_tool = None
                while True:
                    event = await event_queue.get()
                    if event.event_type == "assistant_chunk":
                        # Stop spinner when assistant starts speaking
                        if current_tool:
                            current_tool = None
                        console.print(event.data.get("content", ""), end="")
                    elif event.event_type == "tool_call":
                        tool_name = event.data.get("tool", "?")
                        tool_args = event.data.get("args", {})
                        current_tool = tool_name
                        console.print(f"\n{format_tool_call(tool_name, tool_args)}", highlight=False)
                    elif event.event_type == "tool_output":
                        tool_name = event.data.get("tool", "?")
                        output = event.data.get("output", "")
                        is_error = event.data.get("is_error", False)
                        current_tool = None
                        console.print(format_tool_result(tool_name, output, is_error), highlight=False)
                    elif event.event_type == "turn_complete":
                        console.print()
                        break
                    elif event.event_type == "error":
                        current_tool = None
                        console.print(
                            f"\n[red]Error: {event.data.get('error', '?')}[/]",
                        )
                        break

            except KeyboardInterrupt:
                console.print("\n[yellow]Use /exit to quit[/]")
            except EOFError:
                break

    finally:
        # Submit shutdown
        shutdown_sub = Submission(
            id=f"sub_{submission_id[0] + 1}",
            operation=Operation(op_type=OpType.SHUTDOWN),
        )
        await submission_queue.put(shutdown_sub)
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass

        # Clear run marker so next session gets a fresh output directory
        from agent.tools._output_dir import clear_run_marker
        clear_run_marker()


async def headless_main(prompt, config, max_iterations=None):
    """Run OR-Intern in headless mode."""
    from agent.core.agent_loop import submission_loop
    from agent.core.tools import ToolRouter, create_builtin_tools

    config.approval.yolo_mode = True

    # Create tool router
    tool_router = ToolRouter()
    for tool in create_builtin_tools():
        tool_router.register(tool)

    # Create queues
    submission_queue = asyncio.Queue()
    event_queue = asyncio.Queue()

    # Start agent loop
    agent_task = asyncio.create_task(
        submission_loop(
            submission_queue,
            event_queue,
            config=config,
            tool_router=tool_router,
            local_mode=True,
            stream=True,
        )
    )

    # Submit prompt
    sub = Submission(
        id="sub_1",
        operation=Operation(
            op_type=OpType.USER_INPUT,
            data={"text": prompt},
        ),
    )
    await submission_queue.put(sub)

    # Wait for completion
    while True:
        event = await event_queue.get()
        if event.event_type == "assistant_chunk":
            chunk = event.data.get("content", event.data.get("chunk", ""))
            _safe_print(chunk)
        elif event.event_type == "turn_complete":
            print()
            break
        elif event.event_type == "error":
            print(f"\nError: {event.data.get('error', '?')}")
            break

    # Shutdown
    shutdown_sub = Submission(
        id="sub_shutdown",
        operation=Operation(op_type=OpType.SHUTDOWN),
    )
    await submission_queue.put(shutdown_sub)
    agent_task.cancel()
    try:
        await agent_task
    except asyncio.CancelledError:
        pass


def cli():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="OR-Intern: Operations Research AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  or-intern                              # Interactive mode
  or-intern "Solve a TSP with 5 cities"  # Headless mode
  or-intern --model openai/qwen3.6-plus
        """,
    )
    parser.add_argument("prompt", nargs="?", help="Headless mode prompt")
    parser.add_argument("-m", "--model", help="Model to use")
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--yolo", action="store_true")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    setup_logging(debug=args.debug)

    from agent.config import Config
    try:
        config = Config.from_env()
    except Exception as e:
        print(f"Config error: {e}, using defaults")
        config = Config()

    if args.model:
        config.current_model.name = args.model
    if args.yolo:
        config.approval.yolo_mode = True

    if args.prompt:
        asyncio.run(headless_main(args.prompt, config, args.max_iterations))
    else:
        asyncio.run(interactive_main(config, args.max_iterations))


if __name__ == "__main__":
    cli()
