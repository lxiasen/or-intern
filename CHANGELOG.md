# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-05-29

### Added

- **Session-scoped workspace**: Each session now has a persistent workspace directory (`outputs/<session_id>/`), files survive across turns, LLM can name files via `filename` parameter
- **Workspace state tracking**: `.workspace_state.json` auto-records file metadata; `context_manager` injects file listing into system prompt each turn
- **Session restore**: `/undo`, `/new`, `/compact`, `/sessions`, `/resume` CLI commands for session lifecycle management
- **Multi-source paper search**: `or_papers` tool now searches arXiv + Semantic Scholar + OpenAlex with deduplication and citation analysis
- **Nested YAML configuration**: Replaced flat JSON with structured `config.yaml` (`model`, `solver`, `session`, `approval`, `messaging` sections), environment variable substitution (`$VAR`, `${VAR:-default}`)
- **Telemetry system**: LLM call tracking, tool execution metrics, solver operation stats, heartbeat auto-save
- **Regression test suite**: 128 tests across 15 dimensions (problem types, model generation, solver selection, etc.)
- **Advanced modeling tools**: `cvxpy_builder`, `robust_builder`, `stochastic_builder`, `uncertainty_modeler`
- **OR-specific context compaction**: Tuned thresholds (85%), larger tail retention (10 messages), smaller per-message cap (30k tokens)
- **Model checker tool**: Pre-solve validation of Pyomo model files
- **Problem templates**: 15 standard OR problem templates (TSP, knapsack, VRP, etc.)
- **Notification subsystem**: Slack gateway with auto-event push for approval/error/turn_complete

### Changed

- Configuration from `configs/cli_config.json` → `config.yaml` (nested YAML structure)
- All config field access uses nested paths (`config.model.name`, `config.solver.default`, etc.)
- Output directory from per-run (`outputs/run_<timestamp>/`) to per-session (`outputs/<session_id>/`)
- `or_papers` from single-source (arXiv only) to multi-source with deduplication
- Messaging types consolidated into `agent.config` (removed duplication in `messaging.models`)
- Provider protocol signature aligned across `base.py`, `slack.py`, `gateway.py`

### Fixed

- Dependency inversion: `config.py` no longer imports from `messaging.models`
- Messaging `NotificationProvider.send()` signature mismatch (1 param vs 4 params)
- `SlackProvider` missing `provider_name` attribute
- Dead code path in `session.py` referencing non-existent `MessagingConfig` fields

### Removed

- `configs/cli_config.json` (replaced by `config.yaml`)
- Legacy `get_run_dir()` / `clear_run_marker()` marker-based output directory system

## [0.4.0] - 2026-05-25

### Added

- NLP support with cyipopt integration
- Session persistence and error recovery
- CI/CD pipeline with GitHub Actions

## [0.3.0] - 2026-05-20

### Added

- Complete documentation system (README, AGENTS, CONTRIBUTING, API docs)
- 6-phase quality gate workflow in system prompt
- Sensitivity analysis with shadow prices and parametric analysis
- Visualization tool (variable charts, gap charts, sensitivity plots)
- Solver comparison tool (HiGHS, SCIP, GLPK)
- Research sub-agent for deep-dive OR topics

## [0.2.0] - 2026-05-15

### Added

- Core OR tool chain: model_builder, solver_selector, solve_job, validate_solution
- Report generator (Markdown output)
- Data handler (CSV/JSON loading)
- or_papers (arXiv search)
- Context management with OR-specific compaction

## [0.1.0] - 2026-05-10

### Added

- Initial fork from ML-Intern
- Removed HuggingFace-specific code
- Basic agent loop with LiteLLM integration
- CLI with interactive and headless modes
- Approval policy system (YOLO mode, cost caps)
