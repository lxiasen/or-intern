"""research_tool for OR-Intern.

Spawns a sub-agent with independent LLM context for focused OR research.
The sub-agent uses read-only tools (web_search, or_papers, read, bash)
and returns a structured summary without polluting the main context.
"""

import logging
import time
from typing import Any

from litellm import Message, acompletion

from agent.core.llm_params import _resolve_llm_params
from agent.core.prompt_caching import with_prompt_caching

logger = logging.getLogger(__name__)

# ── Context budget ──
_CONTEXT_WARN = 100_000
_CONTEXT_MAX = 150_000

# ── Read-only research tools ──
RESEARCH_TOOL_NAMES = {
    "web_search",
    "or_papers",
    "read",
    "bash",
}

# ── OR research system prompt ──

RESEARCH_SYSTEM_PROMPT = """\
You are an OR research sub-agent for an operations research assistant.
Your job: research optimization methods, algorithms, and best practices,
then summarize your findings concisely for the main agent.

# Research approach

1. **Search the web**: Use `web_search` to find relevant algorithms, solvers,
   benchmark results, and implementation guides for the problem.
2. **Search papers**: Use `or_papers` to find academic literature on arXiv.
   Focus on recent papers with strong results.
3. **Read code/docs**: Use `read` to inspect any referenced files.
4. **Run quick tests**: Use `bash` for simple computational checks.

# Output format

Your output MUST be structured:

## Problem Analysis
- Problem type classification (LP, MIP, NLP, etc.)
- Known benchmarks and standard test instances

## Recommended Methods
For each promising approach, report:
- **Method**: algorithm/solver name and approach
- **Why it works**: key insight or advantage
- **References**: paper titles, URLs, or code repositories
- **Expected performance**: solve time, optimality guarantees

## Implementation Notes
- Solver compatibility notes
- Parameter tuning recommendations
- Known pitfalls and limitations

Be concise. 300-800 words. Every claim must cite a source.
"""

# ── Tool spec ──

RESEARCH_TOOL_SPEC = {
    "name": "research",
    "description": (
        "Spawn a research sub-agent to explore OR topics, algorithms, "
        "and literature WITHOUT polluting the main conversation. "
        "The sub-agent has its own context with web_search, or_papers, "
        "and read tools. Use for: researching solver algorithms, "
        "finding benchmark results, exploring problem formulations."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": (
                    "Research topic. Be specific: include problem type, "
                    "domain, and what you need. Example: "
                    "'Research the best exact algorithm for Capacitated "
                    "Vehicle Routing Problem with Time Windows (CVRPTW). "
                    "Find benchmark instances and solver performance.'"
                ),
            },
            "context": {
                "type": "string",
                "description": "Optional conversation context for the sub-agent",
            },
        },
        "required": ["task"],
    },
}


# ── Helper: resolve research model ──

def _get_research_model(main_model: str) -> str:
    """Use the same model for research (no cheap fallback needed for qwen)."""
    return main_model


async def research_handler(
    arguments: dict[str, Any], session=None, tool_call_id: str | None = None, **_kw
) -> tuple[str, bool]:
    """Execute research sub-agent."""
    task = arguments.get("task", "")
    context = arguments.get("context", "")

    if not task:
        return "No research task provided.", False
    if not session:
        return "No session available.", False

    # Build independent context
    messages: list[Message] = [
        Message(role="system", content=RESEARCH_SYSTEM_PROMPT),
    ]

    user_content = f"Research task: {task}"
    if context:
        user_content = f"Context: {context}\n\n{user_content}"
    messages.append(Message(role="user", content=user_content))

    # Use same model for research
    research_model = _get_research_model(session.config.model_name)
    llm_params = _resolve_llm_params(
        research_model,
        getattr(session, "hf_token", None),
    )

    # Filter to read-only tools
    tool_specs = [
        spec for spec in session.tool_router.get_tool_specs_for_llm()
        if spec["function"]["name"] in RESEARCH_TOOL_NAMES
    ]

    # Send progress event
    async def _log(text: str):
        try:
            from agent.core.session import Event
            await session.send_event(Event(
                event_type="tool_log",
                data={"tool": "research", "log": text},
            ))
        except Exception:
            pass

    await _log(f"Researching: {task[:80]}...")

    # Sub-agent loop
    final_summary = ""
    for iteration in range(15):
        # Check context budget
        total_chars = sum(len(m.content or "") for m in messages)
        if total_chars > _CONTEXT_MAX:
            final_summary = "(Context limit reached — wrapping up)"
            break

        if total_chars > _CONTEXT_WARN and not final_summary:
            messages.append(Message(
                role="user",
                content="[Context budget running low. Summarize your findings now and skip further tool calls.]"
            ))

        try:
            prepared_messages, prepared_tools = with_prompt_caching(
                messages, tool_specs, llm_params.get("model")
            )

            response = await acompletion(
                messages=prepared_messages,
                tools=prepared_tools if iteration < 12 else None,
                tool_choice="auto" if iteration < 12 else "none",
                max_tokens=2000,
                **llm_params,
            )

            msg = response.choices[0].message

            # If no tool calls, we got our answer
            if not msg.tool_calls:
                final_summary = msg.content or ""
                break

            # Add assistant message with tool calls
            messages.append(msg)

            # Execute tools and add results
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = __import__("json").loads(tc.function.arguments)
                except Exception:
                    fn_args = {}

                # Execute via session's tool router
                try:
                    tool_result, is_error = await session.tool_router.call_tool(
                        fn_name, fn_args, session=session
                    )
                    result_text = tool_result[:3000]  # Truncate long results
                except Exception as e:
                    result_text = f"Tool error: {e}"
                    is_error = True

                messages.append(Message(
                    role="tool",
                    content=result_text,
                    tool_call_id=tc.id,
                ))

                # Brief log for progress
                if fn_name == "web_search":
                    await _log(f"Searched: {fn_args.get('query', '')[:50]}...")
                elif fn_name == "or_papers":
                    await _log(f"Found papers for: {fn_args.get('query', '')[:50]}...")

        except Exception as e:
            logger.error(f"Research sub-agent error: {e}")
            final_summary = f"Research failed: {e}"
            break

    await _log("Research complete")

    if not final_summary:
        final_summary = "(Research agent produced no output)"

    return f"## Research Results\n\n{final_summary}", False
