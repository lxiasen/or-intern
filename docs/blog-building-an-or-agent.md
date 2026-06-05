# Building an OR Agent: From ML-Intern to Domain-Specific AI

## Why Operations Research?

There's a strange paradox in Operations Research. The math is elegant — linear programming, duality theory, network flows — but the tooling is brutal. To solve a real-world optimization problem, you need to:

1. Read a business description ("we have 3 warehouses, 5 customers, minimize shipping cost")
2. Formulate it mathematically (decision variables, objective function, constraints)
3. Translate that into solver-specific code (Pyomo, cvxpy, GAMS)
4. Interpret the results (shadow prices, reduced costs, sensitivity)
5. Explain it to a non-technical stakeholder

Steps 1→3 is where most people get stuck. It's not that the math is hard — it's that the translation from "business problem" to "mathematical model" requires a mental leap that takes years of practice to develop. A junior engineer might spend a day formulating what an experienced OR practitioner does in 10 minutes.

This is exactly the kind of task LLMs should be good at. The knowledge exists in training data — textbooks, Stack Overflow, OR forums. The reasoning is structured — there are clear patterns (minimize cost subject to capacity constraints). And the output is well-defined — a Pyomo model with variables, constraints, and an objective.

But there's a gap between "generate some code" and "solve a real problem." A single LLM call can produce a model, but it can't:
- Verify that the model is correct
- Choose the right solver for the problem type
- Detect infeasibility and suggest reformulations
- Interpret sensitivity results for the business context

That gap is what an agent can fill. Not just one LLM call, but a coordinated workflow with specialized tools, quality gates, and iterative refinement.

## What ML-Intern Gave Us

We didn't start from zero. ML-Intern is an open-source AI agent framework built for machine learning tasks. It provides the infrastructure that every agent needs:

- **Agent Loop**: The event loop that orchestrates LLM calls, tool execution, user interaction, and error recovery
- **Context Manager**: Automatic context compression when conversations exceed the LLM's window
- **Doom Loop Detection**: Prevents the agent from retrying the same failing operation indefinitely
- **Approval Policy**: A safety system that requires human confirmation for expensive or dangerous operations
- **Session Persistence**: Saves conversation trajectories for debugging and replay

Building this infrastructure from scratch would take 3-4 months. Forking it and adapting it to OR took 2 weeks.

But "adapting" undersells the work. Every layer needed changes — some cosmetic, some fundamental.

## The 6-Phase Workflow: Design Thinking

### Core Design Philosophy

OR-Intern adopts a six-phase quality-gate workflow, designed based on a deep understanding of OR problem characteristics:

```
Phase 1: MODEL     → Generate mathematical model
Phase 2: SOLVE     → Select solver and execute
  ┌── Quality Gate ──┐
  │ OPTIMAL, gap≈0   │→ Continue to Phase 3
  │ gap>5% / slow    │→ Try compare_solvers (max 3 attempts)
  │ INFEASIBLE       │→ Diagnose infeasibility, suggest fixes
  └──────────────────┘
Phase 3: VALIDATE  → Verify constraint satisfaction
Phase 4: ANALYZE   → Sensitivity analysis (shadow prices, reduced costs)
Phase 5: VISUALIZE → Generate charts
Phase 6: REPORT    → Create comprehensive report
```

### Why Quality-Gate Iteration?

OR problems have clear success criteria: the solver finds an optimal solution (gap = 0) or it doesn't. Once an optimal solution is obtained, further iteration is pointless. Therefore, we adopt a **quality-gate iteration** strategy:

- Iterate when solution quality is unacceptable
- Stop when solution quality meets the threshold
- **Always complete the full analysis pipeline**

### Quality Gate Logic

The quality gate sits between Phase 2 (SOLVE) and Phase 3 (VALIDATE):

- **OPTIMAL with solve time < 5s**: Proceed directly to Phase 3-6
- **Gap > 5% or solve time > 60s**: Try `compare_solvers` to test HiGHS, SCIP, and Gurobi (if available). If still suboptimal, try adjusting solver parameters. After at most 3 improvement attempts, proceed anyway.
- **INFEASIBLE or UNBOUNDED**: Use `sensitivity_analysis` to diagnose constraint conflicts. Suggest constraint relaxation or model fixes. **Do NOT proceed to report** — there's no valid solution to report.
- **Feasible solution exists**: Always complete Phase 3-6. Users expect a complete analysis, not just a number.

### Why Not Just "Follow Best Practices"?

Why encode this as a hard workflow instead of just telling the LLM to "follow OR best practices"?

Because LLMs are optimizers. They take the shortest path to a "good enough" answer. Without explicit phase structure, the LLM will generate a model, run it, and report the result — skipping validation, sensitivity analysis, and visualization. These extra tasks have no immediate payoff from the LLM's perspective.

The 6-phase workflow is a **commitment device**. It forces the LLM to do the work that makes the difference between "a number" and "an answer."

The explicit instruction **"Do NOT stop after solving! Users expect a complete analysis"** is the critical fix. Without it, even a 6-phase prompt would collapse back to 3 phases in practice.

## Challenges and Solutions

### Challenge 1: Mathematical Notation in Code

LLMs are trained on natural language and code, but OR modeling sits at the intersection. A Pyomo constraint like:

```python
model.c1 = Constraint(expr=model.x[1] + model.x[2] <= 10)
```

is code, but the reasoning behind it is mathematical. The LLM needs to understand that "x₁ + x₂ ≤ 10" translates to `model.x[1] + model.x[2] <= 10` — and that the direction of the inequality matters.

**Solution**: We added `model_checker` as a pre-solve validation tool. It checks:
- All variables referenced in constraints are declared
- Constraint directions are correct (<= vs >=)
- Objective function references valid variables
- Solver is compatible with the problem type

This catches many errors before the solve attempt, saving time and preventing confusing error messages.

### Challenge 2: Infeasibility Diagnosis

An infeasible model means "no solution satisfies all constraints." This is a common user error — they over-constrain the problem. But the raw solver output just says "INFEASIBLE" with no explanation.

**Solution**: When the Quality Gate detects infeasibility, the agent enters a diagnostic loop:
1. Remove constraints one by one to find the minimal infeasible subset
2. Report which constraints conflict
3. Suggest relaxations (e.g., "constraint c3 and c5 conflict — try relaxing c5 from <= to <=")

This required custom logic in `solve_job` that goes beyond standard solver output.

### Challenge 3: Context Window Management

OR problems generate structured output — model code, solver logs, sensitivity tables, validation results. A single solve can produce 10,000+ characters of output. Over multiple conversation turns, this fills the context window fast.

**Solution**: We tuned the context manager for OR-specific patterns:
- **Lower threshold (85%)**: OR conversations generate more structured output than general chat
- **Smaller per-message cap (30k chars)**: Solver output can be very long
- **Larger tail retention (10 messages)**: Recent tool outputs are critical for the LLM's reasoning
- **Solve log summarization**: Compresses verbose solver output into structured summaries (status, gap, time, key variables)

## Real-World Example: Semiconductor Material Shortage Prediction

Let's demonstrate OR-Intern's capabilities with a real-world case.

### Problem Description

A semiconductor manufacturer needs to analyze material shortage risks for the next 8 weeks, based on:
- Current inventory, safety stock, and lead times for 10 materials
- Production plans for 3 products
- Bill of Materials (BOM)

### Usage

```bash
# Prepare data files (CSV format)
# test_data/materials.csv - Material master data
# test_data/production_plan.csv - Production plan
# test_data/bom.csv - Bill of Materials

uv run or-intern "Analyze material shortage risk for semiconductor manufacturing. Data files are in test_data/ directory"
```

### System Execution Flow

```
Phase 1: Model
├── Read CSV data (materials, BOM, production plan)
├── Generate MRP optimization model (Pyomo)
└── Validate model with model_checker

Phase 2: Solve
├── Use HiGHS solver
├── Identify shortage risks (which materials, when, how much)
└── Quality gate: OPTIMAL, gap≈0

Phase 3: Validate
└── Verify all constraints satisfied

Phase 4: Analyze
└── Sensitivity analysis: identify bottleneck materials

Phase 5: Visualize
├── Inventory trend charts (multi-subplot, one per material)
├── Shortage risk heatmap
├── Reorder suggestions chart
└── Supplier cost distribution pie chart

Phase 6: Report
└── Generate complete analysis report (Markdown)
```

### Output Results

**Analysis Summary:**
| Priority | Material | Reorder Qty | Latest Order | Cost |
|:--------:|:---------|:-----------:|:------------:|:----:|
| Urgent | Silicon Wafer | 6,660 | Week 1 | $169,830 |
| Urgent | Metal Target | 618 | Week 1 | $27,810 |
| Important | Etching Gas | 2,756 | Week 2 | $23,426 |

**Output Files:**
```
outputs/2026-06-04_xxxxxxxx/
├── report.md                    # Complete analysis report
├── material_shortage_model.py   # MRP optimization model
├── shortage_analysis_result.json # Analysis result data
├── inventory_trend.png          # Inventory trend chart
├── shortage_heatmap.png         # Shortage risk heatmap
├── reorder_suggestions.png      # Reorder suggestions chart
└── supplier_pie.png             # Supplier cost distribution
```

### Key Capabilities Demonstrated

1. **Data Processing**: Automatically reads CSV files, understands relationships between materials, BOM, and production plans
2. **Model Building**: Generates MRP optimization model (not simple LP/MIP)
3. **Error Recovery**: Automatically switches to hand-written code when model_builder fails
4. **Complete Workflow**: Automatically completes all 6 phases without manual intervention
5. **Professional Output**: Generates professional analysis reports and visualizations

## Try It

```bash
git clone https://github.com/or-intern/or-intern.git
cd or-intern
uv sync
cp .env.example .env  # add your API key

# Simple problem
uv run or-intern "Maximize 5x + 3y subject to 2x + y <= 20, x + 3y <= 30"

# Real-world business scenario
uv run or-intern "Analyze material shortage risk for semiconductor manufacturing. Data files are in test_data/ directory"
```

The agent will walk you through: data loading → model generation → solving → validation → visualization → report.

---

*OR-Intern is open-source under Apache 2.0. Contributions welcome at [github.com/or-intern/or-intern](https://github.com/or-intern/or-intern).*
