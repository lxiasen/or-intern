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
    console.print(f"  [dim]Model: {config.model_name}[/]")
    console.print()
    console.print("  [dim]输入优化问题并按 Enter 开始[/]")
    console.print("  [dim]命令: /help, /model, /exit[/]")
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
                        console.print("[yellow]再见！[/]")
                        break
                    elif cmd == "help":
                        console.print("[bold]可用命令:[/]")
                        console.print("  /help   - 显示帮助信息")
                        console.print("  /model  - 显示当前模型")
                        console.print("  /exit   - 退出程序")
                        console.print()
                        console.print("[bold]示例问题:[/]")
                        console.print("  • 最大化 5x + 3y，约束：2x + y <= 20, x + 3y <= 30")
                        console.print("  • 求解背包问题，容量50，物品重量[10,20,30]，价值[60,100,120]")
                        console.print("  • 列出所有可用的问题模板")
                        continue
                    elif cmd == "model":
                        console.print(f"当前模型: {config.model_name}")
                        continue
                    else:
                        console.print(f"[red]未知命令: {cmd}，输入 /help 查看帮助[/]")
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

    config.yolo_mode = True

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
        config.model_name = args.model
    if args.yolo:
        config.yolo_mode = True

    if args.prompt:
        asyncio.run(headless_main(args.prompt, config, args.max_iterations))
    else:
        asyncio.run(interactive_main(config, args.max_iterations))


if __name__ == "__main__":
    cli()
