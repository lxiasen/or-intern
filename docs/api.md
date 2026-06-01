# OR-Intern API Documentation

All tools are async functions returning `(output: str, is_error: bool)` tuples.

Tool output files are written to the session workspace `outputs/<session_id[:8]>/` and persist across conversation turns.

## Table of Contents

- [Core OR Tools](#core-or-tools)
  - [model_builder](#model_builder) — Pyomo mathematical modeling
  - [cvxpy_builder](#cvxpy_builder) — Convex optimization modeling (cvxpy)
  - [robust_builder](#robust_builder) — Robust optimization modeling
  - [stochastic_builder](#stochastic_builder) — Stochastic programming modeling
  - [problem_templates](#problem_templates) — Standard OR problem templates
  - [model_checker](#model_checker) — Model validation
  - [solver_selector](#solver_selector) — Solver recommendation
  - [solve_job](#solve_job) — Solve execution
  - [validate_solution](#validate_solution) — Solution validation
  - [sensitivity_analysis](#sensitivity_analysis) — Sensitivity analysis
  - [visualization](#visualization) — Visualization
  - [compare_solvers](#compare_solvers) — Solver comparison
  - [report_generator](#report_generator) — Report generation
  - [or_papers](#or_papers) — Multi-source paper search
  - [data_handler](#data_handler) — Data loading
  - [research](#research) — Sub-agent research
- [Infrastructure Tools](#infrastructure-tools)
  - [plan_tool](#plan_tool) — Task planning
  - [notify](#notify) — External notifications
  - [bash / read / write / edit](#bash--read--write--edit) — File system operations

---

## Core OR Tools

### model_builder

Generate Pyomo mathematical models from natural language descriptions. Supports LP, MIP, binary, integer, SOS, indicator constraints, piecewise functions.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `description` | string | ✅ | Problem description, e.g., "maximize 3x+2y s.t. x+y<=10" |
| `solver` | string | | Solver name (default: highs) |
| `filename` | string | | Output filename (e.g., "model_v1.py"). Auto-versioned if omitted |

**Returns**: Model file path, problem type, variables, constraint count

**Example**:
```
description: "maximize 3x + 2y subject to x + y <= 10, x >= 0, y >= 0"
filename: "model_production.py"
→ Model file: outputs/a3f7b2c1/model_production.py
```

---

### cvxpy_builder

Generate cvxpy convex optimization model code. Supports LP, QP, SOCP, SDP with automatic DCP compliance checking.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `description` | string | ✅ | Problem description |
| `solver` | string | | Solver: ECOS, SCS, OSQP, MOSEK (default: ECOS) |
| `filename` | string | | Output filename. Auto-versioned if omitted |

---

### robust_builder

Generate robust optimization models. Supports box and ellipsoidal uncertainty sets.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `description` | string | ✅ | Problem description (with uncertainty parameters) |
| `uncertainty_set` | string | | "box" or "ellipsoidal" (default: box) |
| `gamma` | number | | Uncertainty budget (default: 1.0) |
| `solver` | string | | Solver (default: highs) |
| `filename` | string | | Output filename |

---

### stochastic_builder

Generate two-stage stochastic programming models (SAA).

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `description` | string | ✅ | Problem description (with uncertainty parameters) |
| `n_scenarios` | integer | | Number of scenarios (default: 100) |
| `solver` | string | | Solver (default: highs) |
| `filename` | string | | Output filename |

---

### problem_templates

List/match/generate from 15 standard OR problem templates.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `operation` | string | | "list", "match", "generate" (default: list) |
| `template_name` | string | | Template name (required for generate), e.g., tsp, knapsack, transportation |
| `description` | string | | Problem description (required for match) |
| `params` | object | | Template parameters |
| `solver` | string | | Solver (default: highs) |
| `filename` | string | | Output filename |

---

### model_checker

Validate Pyomo model files for syntax, imports, variables, objective function, constraints, solver compatibility.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `model_path` | string | ✅ | Model file path |
| `run_import_test` | boolean | | Whether to run import test (default: true) |

**Returns**: Validation results (error/warning list)

---

### solver_selector

Recommend the best solver based on problem type.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `description` | string | ✅ | Problem description |
| `prefer_open_source` | boolean | | Prefer open-source solvers (default: true) |

**Returns**: Recommended solver, type (open-source/commercial), rationale, Pyomo usage

---

### solve_job

Execute optimization solve with real-time progress monitoring (gap, bound, nodes).

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `operation` | string | | "run" (execute) or "status" (check available solvers) |
| `model_path` | string | ✅(run) | Pyomo model file path |
| `solver` | string | | Solver (default: highs) |
| `timeout` | integer | | Timeout in seconds (default: 300) |
| `stream_progress` | boolean | | Real-time progress reporting (default: true) |

**Returns**: Status, Objective, Gap, Lower/Upper Bound, Solver Time, variable values

**Example**:
```
model_path: "outputs/a3f7b2c1/model.py"
solver: "highs"
→ ## Solve Results
  Status: OPTIMAL
  Objective value: 30.0
  Gap: 0
  x = 10.0, y = 0.0
```

---

### validate_solution

Validate solution feasibility.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `model_path` | string | ✅ | Model file path |
| `solution` | object | | Solution variable values, e.g., {"x": 10, "y": 0} |

**Returns**: FEASIBLE/INFEASIBLE, violation count, binding constraints list

---

### sensitivity_analysis

Sensitivity analysis: shadow prices, reduced costs, parametric analysis.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `model_path` | string | ✅ | Model file path |
| `solver` | string | | Solver (default: highs) |
| `operation` | string | | "dual", "parametric", "full" (default: full) |

**Returns**: Shadow prices table, reduced costs table, parametric analysis results

---

### visualization

Generate visualization charts (PNG).

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `chart_type` | string | | "variables", "sensitivity", "heatmap", "pareto", "all" |
| `variables` | object | | Variable values, e.g., {"x": 10, "y": 0} |
| `objective` | number | | Objective function value |
| `param_data` | array | | Sensitivity data |
| `gap_data` | array | | Solve progress data |
| `constraints` | object | | Constraint slack values |
| `pareto_data` | array | | Pareto front data |
| `filename_prefix` | string | | Filename prefix (e.g., "iteration2"). Auto-versioned if omitted |

**Returns**: Chart file paths (PNG)

---

### compare_solvers

Multi-solver performance comparison.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `model_path` | string | ✅ | Model file path |
| `solvers` | string | | Comma-separated solver list (default: highs,scip,glpk) |
| `timeout` | integer | | Timeout per solver (default: 60) |

**Returns**: Comparison table (solver, status, time, objective value)

---

### report_generator

Generate comprehensive reports (Markdown or LaTeX).

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `problem_description` | string | | Problem description |
| `objective` | number | | Objective value |
| `variables` | object | | Variable values |
| `constraints` | object | | Constraint shadow prices |
| `solver` | string | | Solver name |
| `status` | string | | Solve status |
| `chart_paths` | array | | Chart path list |
| `format` | string | | "markdown" or "latex" (default: markdown) |
| `filename` | string | | Output filename. Auto-versioned if omitted |

**Returns**: Report file path

---

### or_papers

Multi-source OR paper search and analysis. Supports arXiv, Semantic Scholar, and OpenAlex data sources.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `operation` | string | | "search" (search), "detail" (details), "cite" (citation analysis) |
| `query` | string | ✅(search) | Search keywords |
| `paper_id` | string | | Paper ID (for detail/cite, supports arXiv ID, DOI, S2 ID) |
| `max_results` | integer | | Maximum results (default: 5) |
| `source` | string | | "arxiv", "semantic_scholar", "openalex", "all" (default: all) |

**Returns**:
- search: Paper list (title, authors, abstract, citation count, links)
- detail: Full metadata + abstract
- cite: Citation analysis (who cited this / what this cited)

---

### data_handler

Load CSV/JSON data and convert to Pyomo format.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `operation` | string | | "load" (load) or "inspect" (inspect structure) |
| `file_path` | string | ✅ | Data file path |

**Returns**: Data structure description or Pyomo-compatible code

---

### research

Sub-agent deep research.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `query` | string | ✅ | Research question |

**Returns**: Research results summary

---

## Infrastructure Tools

### plan_tool

Task planning and tracking.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `action` | string | | "create", "update", "list" |
| `todos` | array | | Task list |

---

### notify

Send out-of-band notifications to configured channels.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|:--:|-------------|
| `destinations` | array | ✅ | Target channel name list |
| `message` | string | ✅ | Notification content |
| `title` | string | | Title |
| `severity` | string | | "info", "success", "warning", "error" |

**Returns**: Send results per channel

---

### bash / read / write / edit

File system operations, parameters consistent with standard shell tools.
