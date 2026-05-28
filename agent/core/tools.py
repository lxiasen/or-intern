"""
Tool system for OR-Intern.

Simplified from ML-Intern — only includes Phase 0 tools:
- local_tools (bash, read, write, edit)
- plan_tool
- notify_tool
- web_search_tool

Future phases will add: model_builder, solve_job, solver_selector, etc.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


# ── ToolSpec and ToolRouter ──

@dataclass
class ToolSpec:
    """Tool specification - the single tool abstraction."""
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Optional[Callable[[dict], Awaitable[tuple]]] = None


class ToolRouter:
    """Central registry for tool registration, conversion, and dispatch."""

    def __init__(self):
        self.tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec):
        """Register a tool."""
        self.tools[tool.name] = tool

    def get_tool_specs_for_llm(self) -> list[dict]:
        """Convert tools to OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in self.tools.values()
        ]

    async def call_tool(self, name, args, session=None, tool_call_id=None):
        """Dispatch tool execution.

        Returns: (output_string, is_error_bool)
        """
        tool_spec = self.tools.get(name)
        if not tool_spec:
            return f"Tool '{name}' not found", True

        if tool_spec.handler is None:
            return f"Tool '{name}' has no handler", True

        try:
            import inspect
            sig = inspect.signature(tool_spec.handler)
            if "session" in sig.parameters:
                result = await tool_spec.handler(args, session=session)
            else:
                result = await tool_spec.handler(args)
            if isinstance(result, tuple):
                return result
            return result, False
        except Exception as e:
            return str(e), True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ── Built-in tool creation ──

from agent.tools.plan_tool import PLAN_TOOL_SPEC, plan_tool_handler
from agent.tools.notify_tool import NOTIFY_TOOL_SPEC, notify_handler
from agent.tools.web_search_tool import WEB_SEARCH_TOOL_SPEC, web_search_handler
from agent.tools.local_tools import get_local_tools
from agent.tools.model_builder import MODEL_BUILDER_TOOL_SPEC, model_builder_handler
from agent.tools.solver_selector import SOLVER_SELECTOR_TOOL_SPEC, solver_selector_handler
from agent.tools.solve_job import SOLVE_JOB_TOOL_SPEC, solve_job_handler
from agent.tools.sensitivity_analysis import SENSITIVITY_ANALYSIS_TOOL_SPEC, sensitivity_analysis_handler
from agent.tools.visualization import VISUALIZATION_TOOL_SPEC, visualization_handler
from agent.tools.report_generator import REPORT_GENERATOR_TOOL_SPEC, report_generator_handler
from agent.tools.validate_solution import VALIDATE_SOLUTION_TOOL_SPEC, validate_solution_handler
from agent.tools.or_papers import OR_PAPERS_TOOL_SPEC, or_papers_handler
from agent.tools.compare_solvers import COMPARE_SOLVERS_TOOL_SPEC, compare_solvers_handler
from agent.tools.research_tool import RESEARCH_TOOL_SPEC, research_handler
from agent.tools.data_handler import DATA_HANDLER_TOOL_SPEC, data_handler_handler
from agent.tools.templates import TEMPLATES_TOOL_SPEC, templates_handler
from agent.tools.model_checker import MODEL_CHECKER_TOOL_SPEC, model_checker_handler


def create_builtin_tools() -> list[ToolSpec]:
    """Create all built-in tools for OR-Intern Phase 2."""
    tools = []

    # Local tools (bash, read, write, edit)
    tools.extend(get_local_tools())

    # Core OR tools (Phase 1)
    tools.append(ToolSpec(
        name=MODEL_BUILDER_TOOL_SPEC["name"],
        description=MODEL_BUILDER_TOOL_SPEC["description"],
        parameters=MODEL_BUILDER_TOOL_SPEC["parameters"],
        handler=model_builder_handler,
    ))
    tools.append(ToolSpec(
        name=SOLVER_SELECTOR_TOOL_SPEC["name"],
        description=SOLVER_SELECTOR_TOOL_SPEC["description"],
        parameters=SOLVER_SELECTOR_TOOL_SPEC["parameters"],
        handler=solver_selector_handler,
    ))
    tools.append(ToolSpec(
        name=SOLVE_JOB_TOOL_SPEC["name"],
        description=SOLVE_JOB_TOOL_SPEC["description"],
        parameters=SOLVE_JOB_TOOL_SPEC["parameters"],
        handler=solve_job_handler,
    ))

    # Phase 2: Analysis & Reporting
    tools.append(ToolSpec(
        name=SENSITIVITY_ANALYSIS_TOOL_SPEC["name"],
        description=SENSITIVITY_ANALYSIS_TOOL_SPEC["description"],
        parameters=SENSITIVITY_ANALYSIS_TOOL_SPEC["parameters"],
        handler=sensitivity_analysis_handler,
    ))
    tools.append(ToolSpec(
        name=VISUALIZATION_TOOL_SPEC["name"],
        description=VISUALIZATION_TOOL_SPEC["description"],
        parameters=VISUALIZATION_TOOL_SPEC["parameters"],
        handler=visualization_handler,
    ))
    tools.append(ToolSpec(
        name=REPORT_GENERATOR_TOOL_SPEC["name"],
        description=REPORT_GENERATOR_TOOL_SPEC["description"],
        parameters=REPORT_GENERATOR_TOOL_SPEC["parameters"],
        handler=report_generator_handler,
    ))

    # Phase 1 completion: validate + papers
    tools.append(ToolSpec(
        name=VALIDATE_SOLUTION_TOOL_SPEC["name"],
        description=VALIDATE_SOLUTION_TOOL_SPEC["description"],
        parameters=VALIDATE_SOLUTION_TOOL_SPEC["parameters"],
        handler=validate_solution_handler,
    ))
    tools.append(ToolSpec(
        name=OR_PAPERS_TOOL_SPEC["name"],
        description=OR_PAPERS_TOOL_SPEC["description"],
        parameters=OR_PAPERS_TOOL_SPEC["parameters"],
        handler=or_papers_handler,
    ))

    # Phase 2 completion: solver comparison
    tools.append(ToolSpec(
        name=COMPARE_SOLVERS_TOOL_SPEC["name"],
        description=COMPARE_SOLVERS_TOOL_SPEC["description"],
        parameters=COMPARE_SOLVERS_TOOL_SPEC["parameters"],
        handler=compare_solvers_handler,
    ))

    # Research sub-agent
    tools.append(ToolSpec(
        name=RESEARCH_TOOL_SPEC["name"],
        description=RESEARCH_TOOL_SPEC["description"],
        parameters=RESEARCH_TOOL_SPEC["parameters"],
        handler=research_handler,
    ))

    # Data handler (Phase 1 completion)
    tools.append(ToolSpec(
        name=DATA_HANDLER_TOOL_SPEC["name"],
        description=DATA_HANDLER_TOOL_SPEC["description"],
        parameters=DATA_HANDLER_TOOL_SPEC["parameters"],
        handler=data_handler_handler,
    ))

    # Problem templates (v0.5)
    tools.append(ToolSpec(
        name=TEMPLATES_TOOL_SPEC["name"],
        description=TEMPLATES_TOOL_SPEC["description"],
        parameters=TEMPLATES_TOOL_SPEC["parameters"],
        handler=templates_handler,
    ))

    # Model checker (v0.5)
    tools.append(ToolSpec(
        name=MODEL_CHECKER_TOOL_SPEC["name"],
        description=MODEL_CHECKER_TOOL_SPEC["description"],
        parameters=MODEL_CHECKER_TOOL_SPEC["parameters"],
        handler=model_checker_handler,
    ))

    # Plan tool
    tools.append(ToolSpec(
        name=PLAN_TOOL_SPEC["name"],
        description=PLAN_TOOL_SPEC["description"],
        parameters=PLAN_TOOL_SPEC["parameters"],
        handler=plan_tool_handler,
    ))

    # Notify tool
    tools.append(ToolSpec(
        name=NOTIFY_TOOL_SPEC["name"],
        description=NOTIFY_TOOL_SPEC["description"],
        parameters=NOTIFY_TOOL_SPEC["parameters"],
        handler=notify_handler,
    ))

    # Web search tool
    tools.append(ToolSpec(
        name=WEB_SEARCH_TOOL_SPEC["name"],
        description=WEB_SEARCH_TOOL_SPEC["description"],
        parameters=WEB_SEARCH_TOOL_SPEC["parameters"],
        handler=web_search_handler,
    ))

    return tools
