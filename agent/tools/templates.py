"""Problem template library for OR-Intern v0.5.

15 standard OR problem templates with parameterized Pyomo code generation.
Known problems use templates for reliable solving; novel problems use LLM.
"""

import logging
import re
from pathlib import Path
from typing import Any

from agent.tools._output_dir import get_workspace_dir, suggest_filename, record_file

logger = logging.getLogger(__name__)

# ── Template registry ──

TEMPLATES: dict[str, dict[str, Any]] = {}


def _register(name: str, description: str, problem_type: str, keywords: list[str]):
    def decorator(func):
        TEMPLATES[name] = {
            "name": name,
            "description": description,
            "problem_type": problem_type,
            "keywords": keywords,
            "generator": func,
        }
        return func
    return decorator


def match_template(description: str) -> str | None:
    """Return the best-matching template name for a natural language description, or None."""
    desc_lower = description.lower()
    scores: dict[str, int] = {}
    for name, tpl in TEMPLATES.items():
        score = sum(1 for kw in tpl["keywords"] if kw in desc_lower)
        if score > 0:
            scores[name] = score
    if not scores:
        return None
    return max(scores, key=scores.get)


def list_templates() -> str:
    """Return a formatted list of all available templates."""
    lines = ["## Available Problem Templates\n"]
    for name, tpl in sorted(TEMPLATES.items()):
        lines.append(f"- **{name}** ({tpl['problem_type']}): {tpl['description']}")
    return "\n".join(lines)


def generate_from_template(template_name: str, params: dict[str, Any], solver: str = "highs") -> str:
    """Generate Pyomo code from a named template with parameters."""
    tpl = TEMPLATES.get(template_name)
    if not tpl:
        available = ", ".join(sorted(TEMPLATES.keys()))
        raise ValueError(f"Unknown template '{template_name}'. Available: {available}")
    return tpl["generator"](params, solver)


# ── Template implementations ──

@_register(
    "tsp",
    "Traveling Salesman Problem — find the shortest route visiting all cities exactly once",
    "MIP",
    ["tsp", "traveling salesman", "travelling salesman", "shortest route", "tour"],
)
def _tsp(params: dict, solver: str) -> str:
    n = params.get("n", 5)
    dist = params.get("distances", None)
    dist_code = ""
    if dist:
        rows = []
        for i in range(n):
            for j in range(n):
                if i != j:
                    rows.append(f"    ({i},{j}): {dist[i][j]}")
        dist_code = "distance = {\n" + ",\n".join(rows) + "\n}"
    else:
        dist_code = (
            f"import random\n"
            f"random.seed(42)\n"
            f"coords = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range({n})]\n"
            f"distance = {{(i,j): ((coords[i][0]-coords[j][0])**2 + (coords[i][1]-coords[j][1])**2)**0.5\n"
            f"          for i in range({n}) for j in range({n}) if i != j}}"
        )

    return f"""\
from pyomo.environ import *
import itertools

model = ConcreteModel()
N = {n}
cities = range(N)

{dist_code}

# Variables
model.x = Var(cities, cities, domain=Binary)
model.u = Var(cities, domain=NonNegativeReals, bounds=(0, N-1))

# Objective: minimize total distance
model.obj = Objective(
    expr=sum(distance[i,j] * model.x[i,j] for i in cities for j in cities if i != j),
    sense=minimize)

# Each city is visited exactly once (in-degree = 1)
model.in_degree = ConstraintList()
for j in cities:
    model.in_degree.add(
        sum(model.x[i,j] for i in cities if i != j) == 1)

# Each city is left exactly once (out-degree = 1)
model.out_degree = ConstraintList()
for i in cities:
    model.out_degree.add(
        sum(model.x[i,j] for j in cities if j != i) == 1)

# Subtour elimination (MTZ formulation)
model.subtour = ConstraintList()
for i in cities:
    for j in cities:
        if i != j and i > 0 and j > 0:
            model.subtour.add(
                model.u[i] - model.u[j] + (N-1)*model.x[i,j] <= N-2)

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

# Extract tour
print("TOUR:")
for i in cities:
    for j in cities:
        if i != j and value(model.x[i,j]) > 0.5:
            print(f"  {{i}} -> {{j}}")
"""


@_register(
    "knapsack",
    "0-1 Knapsack Problem — maximize value within weight capacity",
    "MIP",
    ["knapsack", "backpack", "0-1 knapsack", "binary knapsack"],
)
def _knapsack(params: dict, solver: str) -> str:
    n = params.get("n", 5)
    capacity = params.get("capacity", 50)
    weights = params.get("weights", None)
    values = params.get("values", None)

    if weights and values:
        w_str = str(weights)
        v_str = str(values)
    else:
        w_str = f"[12, 7, 11, 8, 9][:{n}]"
        v_str = f"[24, 13, 23, 15, 16][:{n}]"

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
N = {n}
items = range(N)

weights = {w_str}
values = {v_str}
capacity = {capacity}

model.x = Var(items, domain=Binary)

model.obj = Objective(
    expr=sum(values[i] * model.x[i] for i in items),
    sense=maximize)

model.weight_constraint = Constraint(
    expr=sum(weights[i] * model.x[i] for i in items) <= capacity)

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

for i in items:
    if value(model.x[i]) > 0.5:
        print(f"  item_{{i}} = 1 (w={{weights[i]}}, v={{values[i]}})")
    else:
        print(f"  item_{{i}} = 0")
"""


@_register(
    "facility_location",
    "Facility Location Problem — decide where to open facilities to minimize total cost",
    "MIP",
    ["facility location", "warehouse", "depot", "plant location", "site selection"],
)
def _facility_location(params: dict, solver: str) -> str:
    n_facilities = params.get("n_facilities", 3)
    n_customers = params.get("n_customers", 5)
    fixed_costs = params.get("fixed_costs", None)
    transport_costs = params.get("transport_costs", None)

    fc_str = str(fixed_costs) if fixed_costs else f"[100, 120, 90][:{n_facilities}]"
    if transport_costs:
        tc_str = str(transport_costs)
    else:
        tc_str = (
            f"[[10, 15, 20, 25, 30],\n"
            f"     [15, 10, 18, 22, 28],\n"
            f"     [20, 18, 10, 15, 20]][:{n_facilities}]"
        )

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
F = {n_facilities}
C = {n_customers}
facilities = range(F)
customers = range(C)

fixed_costs = {fc_str}
transport_costs = {tc_str}

model.y = Var(facilities, domain=Binary)  # 1 if facility is open
model.x = Var(facilities, customers, domain=NonNegativeReals)  # fraction of demand served

# Objective: minimize fixed + transport costs
model.obj = Objective(
    expr=sum(fixed_costs[f] * model.y[f] for f in facilities)
       + sum(transport_costs[f][c] * model.x[f,c] for f in facilities for c in customers),
    sense=minimize)

# Each customer's demand must be fully met
model.demand = ConstraintList()
for c in customers:
    model.demand.add(
        sum(model.x[f,c] for f in facilities) == 1)

# Can only serve from open facilities
model.capacity = ConstraintList()
for f in facilities:
    for c in customers:
        model.capacity.add(
            model.x[f,c] <= model.y[f])

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("OPEN FACILITIES:")
for f in facilities:
    if value(model.y[f]) > 0.5:
        print(f"  Facility {{f}} is OPEN")
"""


@_register(
    "transportation",
    "Transportation Problem — minimize cost of shipping from sources to destinations",
    "LP",
    ["transportation", "shipping", "supply chain", "allocation"],
)
def _transportation(params: dict, solver: str) -> str:
    n_supply = params.get("n_supply", 3)
    n_demand = params.get("n_demand", 4)
    supply = params.get("supply", None)
    demand = params.get("demand", None)
    costs = params.get("costs", None)

    s_str = str(supply) if supply else f"[30, 50, 20][:{n_supply}]"
    d_str = str(demand) if demand else f"[15, 25, 30, 30][:{n_demand}]"
    if costs:
        c_str = str(costs)
    else:
        c_str = (
            f"[[2, 3, 4, 5],\n"
            f"     [3, 2, 5, 3],\n"
            f"     [4, 3, 2, 4]][:{n_supply}]"
        )

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
S = {n_supply}
D = {n_demand}
sources = range(S)
dests = range(D)

supply = {s_str}
demand = {d_str}
costs = {c_str}

model.x = Var(sources, dests, domain=NonNegativeReals)

model.obj = Objective(
    expr=sum(costs[i][j] * model.x[i,j] for i in sources for j in dests),
    sense=minimize)

model.supply_con = ConstraintList()
for i in sources:
    model.supply_con.add(
        sum(model.x[i,j] for j in dests) <= supply[i])

model.demand_con = ConstraintList()
for j in dests:
    model.demand_con.add(
        sum(model.x[i,j] for i in sources) >= demand[j])

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("SHIPMENTS:")
for i in sources:
    for j in dests:
        v = value(model.x[i,j])
        if v > 0.01:
            print(f"  source_{{i}} -> dest_{{j}}: {{v:.1f}}")
"""


@_register(
    "blending",
    "Blending Problem — mix ingredients to meet requirements at minimum cost",
    "LP",
    ["blending", "mixing", "recipe", "diet problem", "feed mix"],
)
def _blending(params: dict, solver: str) -> str:
    n_ingredients = params.get("n_ingredients", 3)
    n_nutrients = params.get("n_nutrients", 2)
    costs = params.get("costs", None)
    composition = params.get("composition", None)
    min_req = params.get("min_requirements", None)
    max_amount = params.get("max_amount", 100)

    c_str = str(costs) if costs else f"[3, 5, 4][:{n_ingredients}]"
    if composition:
        comp_str = str(composition)
    else:
        comp_str = f"[[0.1, 0.3], [0.2, 0.1], [0.15, 0.2]][:{n_ingredients}]"
    mr_str = str(min_req) if min_req else f"[0.15, 0.2][:{n_nutrients}]"

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
I = {n_ingredients}
N = {n_nutrients}
ingredients = range(I)
nutrients = range(N)

costs = {c_str}
composition = {comp_str}
min_req = {mr_str}
max_amount = {max_amount}

model.x = Var(ingredients, domain=NonNegativeReals, bounds=(0, max_amount))

model.obj = Objective(
    expr=sum(costs[i] * model.x[i] for i in ingredients),
    sense=minimize)

# Nutrient requirements
model.nutrition = ConstraintList()
for n in nutrients:
    model.nutrition.add(
        sum(composition[i][n] * model.x[i] for i in ingredients) >= min_req[n])

# Total amount = 1 (proportions)
model.total = Constraint(
    expr=sum(model.x[i] for i in ingredients) == 1)

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("BLEND:")
for i in ingredients:
    print(f"  ingredient_{{i}}: {{value(model.x[i]):.4f}}")
"""


@_register(
    "portfolio",
    "Portfolio Optimization — maximize return for a given risk level (Markowitz model)",
    "QP",
    ["portfolio", "investment", "asset allocation", "markowitz", "risk return"],
)
def _portfolio(params: dict, solver: str) -> str:
    n_assets = params.get("n_assets", 4)
    returns = params.get("returns", None)
    max_risk = params.get("max_risk", 0.04)

    r_str = str(returns) if returns else f"[0.10, 0.12, 0.08, 0.15][:{n_assets}]"

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
N = {n_assets}
assets = range(N)

returns = {r_str}
max_risk = {max_risk}

# Simplified: assume diagonal covariance (independent assets)
variances = [0.04, 0.06, 0.03, 0.08][:N]

model.w = Var(assets, domain=NonNegativeReals, bounds=(0, 1))

# Maximize expected return
model.obj = Objective(
    expr=sum(returns[i] * model.w[i] for i in assets),
    sense=maximize)

# Weights sum to 1
model.budget = Constraint(
    expr=sum(model.w[i] for i in assets) == 1)

# Risk constraint (variance <= max_risk)
model.risk = Constraint(
    expr=sum(variances[i] * model.w[i]**2 for i in assets) <= max_risk)

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("ALLOCATION:")
for i in assets:
    print(f"  asset_{{i}}: {{value(model.w[i]):.4f}} (return={{returns[i]}})")
"""


@_register(
    "workforce_scheduling",
    "Workforce Scheduling — assign workers to shifts to meet demand at minimum cost",
    "MIP",
    ["workforce", "shift scheduling", "staff scheduling", "nurse scheduling", "employee scheduling"],
)
def _workforce_scheduling(params: dict, solver: str) -> str:
    n_days = params.get("n_days", 7)
    n_shifts = params.get("n_shifts", 3)
    demand = params.get("demand", None)
    cost_per_shift = params.get("cost_per_shift", 100)

    d_str = str(demand) if demand else f"[3, 4, 3, 5, 4, 3, 2][:{n_days}]"

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
D = {n_days}
S = {n_shifts}
days = range(D)
shifts = range(S)

demand = {d_str}
cost = {cost_per_shift}
max_consecutive = 5

model.x = Var(days, shifts, domain=Binary)

model.obj = Objective(
    expr=sum(cost * model.x[d,s] for d in days for s in shifts),
    sense=minimize)

# Meet demand each day
model.cover = ConstraintList()
for d in days:
    model.cover.add(
        sum(model.x[d,s] for s in shifts) >= demand[d])

# Max consecutive days
model.consecutive = ConstraintList()
for s in shifts:
    for d_start in range(D - max_consecutive):
        model.consecutive.add(
            sum(model.x[d,s] for d in range(d_start, d_start + max_consecutive + 1)) <= max_consecutive)

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("SCHEDULE:")
for d in days:
    assigned = [s for s in shifts if value(model.x[d,s]) > 0.5]
    print(f"  Day {{d}}: shifts {{assigned}} (demand={{demand[d]}})")
"""


@_register(
    "set_cover",
    "Set Cover Problem — select minimum-cost subsets to cover all elements",
    "MIP",
    ["set cover", "covering", "minimum cover"],
)
def _set_cover(params: dict, solver: str) -> str:
    n_sets = params.get("n_sets", 5)
    n_elements = params.get("n_elements", 6)
    costs = params.get("costs", None)
    coverage = params.get("coverage", None)

    c_str = str(costs) if costs else f"[5, 8, 3, 7, 4][:{n_sets}]"
    if coverage:
        cov_str = str(coverage)
    else:
        cov_str = (
            f"{{0: [0,1], 1: [1,2], 2: [0,2,3], 3: [3,4], 4: [4,5]}}"
        )

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
S = {n_sets}
E = {n_elements}
sets = range(S)
elements = range(E)

costs = {c_str}
coverage = {cov_str}

model.x = Var(sets, domain=Binary)

model.obj = Objective(
    expr=sum(costs[s] * model.x[s] for s in sets),
    sense=minimize)

model.cover = ConstraintList()
for e in elements:
    covering_sets = [s for s in sets if e in coverage.get(s, [])]
    model.cover.add(
        sum(model.x[s] for s in covering_sets) >= 1)

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("SELECTED SETS:")
for s in sets:
    if value(model.x[s]) > 0.5:
        print(f"  Set {{s}} (cost={{costs[s]}}, covers={{coverage.get(s, [])}})")
"""


@_register(
    "bin_packing",
    "Bin Packing Problem — pack items into minimum number of bins",
    "MIP",
    ["bin packing", "packing", "container loading"],
)
def _bin_packing(params: dict, solver: str) -> str:
    n_items = params.get("n_items", 6)
    bin_capacity = params.get("bin_capacity", 10)
    sizes = params.get("sizes", None)
    n_bins = params.get("n_bins", None)

    if n_bins is None:
        n_bins = n_items
    s_str = str(sizes) if sizes else f"[4, 5, 3, 7, 2, 6][:{n_items}]"

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
I = {n_items}
B = {n_bins}
items = range(I)
bins = range(B)

sizes = {s_str}
capacity = {bin_capacity}

model.y = Var(bins, domain=Binary)  # 1 if bin is used
model.x = Var(items, bins, domain=Binary)  # 1 if item i is in bin j

model.obj = Objective(
    expr=sum(model.y[j] for j in bins),
    sense=minimize)

# Each item in exactly one bin
model.assign = ConstraintList()
for i in items:
    model.assign.add(
        sum(model.x[i,j] for j in bins) == 1)

# Bin capacity
model.capacity_con = ConstraintList()
for j in bins:
    model.capacity_con.add(
        sum(sizes[i] * model.x[i,j] for i in items) <= capacity * model.y[j])

# Can only assign to used bins
model.link = ConstraintList()
for i in items:
    for j in bins:
        model.link.add(model.x[i,j] <= model.y[j])

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("PACKING:")
for j in bins:
    if value(model.y[j]) > 0.5:
        items_in = [i for i in items if value(model.x[i,j]) > 0.5]
        total = sum(sizes[i] for i in items_in)
        print(f"  Bin {{j}}: items={{items_in}}, total_size={{total}}/{{capacity}}")
"""


@_register(
    "production_planning",
    "Production Planning — plan production quantities to meet demand at minimum cost",
    "LP",
    ["production planning", "production scheduling", "manufacturing", "aggregate planning"],
)
def _production_planning(params: dict, solver: str) -> str:
    n_periods = params.get("n_periods", 4)
    n_products = params.get("n_products", 2)
    demand = params.get("demand", None)
    prod_cost = params.get("prod_cost", None)
    capacity = params.get("capacity", 100)

    if demand:
        d_str = str(demand)
    else:
        d_str = f"[[30, 40, 50, 35], [20, 25, 30, 25]][:{n_products}]"
    pc_str = str(prod_cost) if prod_cost else f"[10, 15][:{n_products}]"

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
T = {n_periods}
P = {n_products}
periods = range(T)
products = range(P)

demand = {d_str}
prod_cost = {pc_str}
capacity = {capacity}

model.x = Var(products, periods, domain=NonNegativeReals)  # production
model.inv = Var(products, periods, domain=NonNegativeReals)  # inventory

model.obj = Objective(
    expr=sum(prod_cost[p] * model.x[p,t] for p in products for t in periods),
    sense=minimize)

# Demand satisfaction (production + inventory = demand + next inventory)
model.flow = ConstraintList()
for p in products:
    for t in periods:
        prev_inv = model.inv[p, t-1] if t > 0 else 0
        model.flow.add(
            model.x[p,t] + prev_inv == demand[p][t] + model.inv[p,t])

# Capacity constraint per period
model.cap = ConstraintList()
for t in periods:
    model.cap.add(
        sum(model.x[p,t] for p in products) <= capacity)

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("PRODUCTION PLAN:")
for p in products:
    for t in periods:
        print(f"  product_{{p}}_period_{{t}}: prod={{value(model.x[p,t]):.1f}} inv={{value(model.inv[p,t]):.1f}}")
"""


@_register(
    "assignment",
    "Assignment Problem — assign agents to tasks at minimum cost",
    "MIP",
    ["assignment", "matching", "task assignment", "job assignment"],
)
def _assignment(params: dict, solver: str) -> str:
    n_agents = params.get("n_agents", 4)
    n_tasks = params.get("n_tasks", 4)
    costs = params.get("costs", None)

    if costs:
        c_str = str(costs)
    else:
        c_str = (
            f"[[9, 2, 7, 8],\n"
            f"     [6, 4, 3, 7],\n"
            f"     [5, 8, 1, 8],\n"
            f"     [7, 6, 9, 4]][:{n_agents}]"
        )

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
A = {n_agents}
T = {n_tasks}
agents = range(A)
tasks = range(T)

costs = {c_str}

model.x = Var(agents, tasks, domain=Binary)

model.obj = Objective(
    expr=sum(costs[i][j] * model.x[i,j] for i in agents for j in tasks),
    sense=minimize)

# Each agent does at most one task
model.agent_con = ConstraintList()
for i in agents:
    model.agent_con.add(
        sum(model.x[i,j] for j in tasks) <= 1)

# Each task done by at most one agent
model.task_con = ConstraintList()
for j in tasks:
    model.task_con.add(
        sum(model.x[i,j] for i in agents) <= 1)

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("ASSIGNMENTS:")
for i in agents:
    for j in tasks:
        if value(model.x[i,j]) > 0.5:
            print(f"  agent_{{i}} -> task_{{j}} (cost={{costs[i][j]}})")
"""


@_register(
    "network_flow",
    "Minimum Cost Network Flow — send flow through a network at minimum cost",
    "LP",
    ["network flow", "min cost flow", "flow network", "supply network"],
)
def _network_flow(params: dict, solver: str) -> str:
    n_nodes = params.get("n_nodes", 4)
    arcs = params.get("arcs", None)
    supply = params.get("supply", None)

    if arcs:
        a_str = str(arcs)
    else:
        a_str = "[(0,1), (0,2), (1,2), (1,3), (2,3)]"
    s_str = str(supply) if supply else "{0: 20, 1: 0, 2: 0, 3: -20}"

    return f"""\
from pyomo.environ import *

model = ConcreteModel()

arcs = {a_str}
capacity = {{a: 15 for a in arcs}}
cost = {{a: 1 for a in arcs}}
supply = {s_str}

model.x = Var(arcs, domain=NonNegativeReals)

model.obj = Objective(
    expr=sum(cost[a] * model.x[a] for a in arcs),
    sense=minimize)

# Capacity constraints
model.cap = ConstraintList()
for a in arcs:
    model.cap.add(model.x[a] <= capacity[a])

# Flow balance at each node
model.balance = ConstraintList()
nodes = set()
for i, j in arcs:
    nodes.add(i)
    nodes.add(j)
for n in nodes:
    inflow = sum(model.x[i,j] for i,j in arcs if j == n)
    outflow = sum(model.x[i,j] for i,j in arcs if i == n)
    model.balance.add(inflow - outflow == supply.get(n, 0))

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("FLOWS:")
for a in arcs:
    v = value(model.x[a])
    if v > 0.01:
        print(f"  arc_{{a[0]}}_{{a[1]}}: {{v:.1f}}")
"""


@_register(
    "job_shop",
    "Job Shop Scheduling — schedule jobs on machines to minimize makespan",
    "MIP",
    ["job shop", "machine scheduling", "shop floor", "job scheduling"],
)
def _job_shop(params: dict, solver: str) -> str:
    n_jobs = params.get("n_jobs", 3)
    n_machines = params.get("n_machines", 3)
    processing_times = params.get("processing_times", None)
    big_m = params.get("big_m", 1000)

    if processing_times:
        pt_str = str(processing_times)
    else:
        pt_str = (
            f"{{(0,0): 3, (0,1): 2, (0,2): 2,\n"
            f"     (1,0): 2, (1,1): 3, (1,2): 1,\n"
            f"     (2,0): 1, (2,1): 2, (2,2): 3}}"
        )

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
J = {n_jobs}
M = {n_machines}
jobs = range(J)
machines = range(M)

p = {pt_str}  # processing time: (job, machine) -> time
big_M = {big_m}

model.start = Var(jobs, machines, domain=NonNegativeReals)
model.makespan = Var(domain=NonNegativeReals)
model.seq = Var(jobs, jobs, machines, domain=Binary)  # sequencing vars

# Minimize makespan
model.obj = Objective(expr=model.makespan, sense=minimize)

# Makespan >= completion of all operations
model.makespan_con = ConstraintList()
for j in jobs:
    last_machine = M - 1
    model.makespan_con.add(
        model.makespan >= model.start[j, last_machine] + p.get((j, last_machine), 1))

# Precedence within each job
model.precedence = ConstraintList()
for j in jobs:
    for m in range(1, M):
        model.precedence.add(
            model.start[j, m] >= model.start[j, m-1] + p.get((j, m-1), 1))

# No overlap on each machine
model.no_overlap = ConstraintList()
for m in machines:
    for j1 in jobs:
        for j2 in jobs:
            if j1 < j2:
                model.no_overlap.add(
                    model.start[j1, m] + p.get((j1, m), 1) <= model.start[j2, m] + big_M * (1 - model.seq[j1, j2, m]))
                model.no_overlap.add(
                    model.start[j2, m] + p.get((j2, m), 1) <= model.start[j1, m] + big_M * model.seq[j1, j2, m])

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("SCHEDULE:")
for j in jobs:
    for m in machines:
        s = value(model.start[j, m])
        print(f"  job_{{j}}_machine_{{m}}: start={{s:.1f}}")
"""


@_register(
    "scheduling",
    "General Scheduling — schedule tasks with precedence and resource constraints",
    "MIP",
    ["scheduling", "task scheduling", "project scheduling", "resource constrained scheduling"],
)
def _scheduling(params: dict, solver: str) -> str:
    n_tasks = params.get("n_tasks", 5)
    duration = params.get("duration", None)
    deadline = params.get("deadline", 20)
    n_resources = params.get("n_resources", 1)
    resource_req = params.get("resource_req", None)
    resource_cap = params.get("resource_cap", None)
    precedence = params.get("precedence", None)

    d_str = str(duration) if duration else f"[3, 5, 2, 4, 3][:{n_tasks}]"
    rr_str = str(resource_req) if resource_req else f"[2, 3, 1, 2, 2][:{n_tasks}]"
    rc_str = str(resource_cap) if resource_cap else f"[4][:{n_resources}]"
    prec_str = str(precedence) if precedence else "[(0,1), (0,2), (1,3), (2,4)]"

    return f"""\
from pyomo.environ import *

model = ConcreteModel()
T = {n_tasks}
R = {n_resources}
tasks = range(T)

duration = {d_str}
resource_req = {rr_str}
resource_cap = {rc_str}
precedence = {prec_str}
deadline = {deadline}

model.start = Var(tasks, domain=NonNegativeReals)
model.makespan = Var(domain=NonNegativeReals)

model.obj = Objective(expr=model.makespan, sense=minimize)

# Makespan
model.makespan_con = ConstraintList()
for t in tasks:
    model.makespan_con.add(
        model.makespan >= model.start[t] + duration[t])

# Precedence
model.precedence_con = ConstraintList()
for i, j in precedence:
    model.precedence_con.add(
        model.start[j] >= model.start[i] + duration[i])

# Deadline
model.deadline_con = ConstraintList()
for t in tasks:
    model.deadline_con.add(model.start[t] + duration[t] <= deadline)

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("SCHEDULE:")
for t in tasks:
    s = value(model.start[t])
    print(f"  task_{{t}}: start={{s:.1f}} end={{s + duration[t]:.1f}}")
"""


@_register(
    "vrp",
    "Vehicle Routing Problem — route vehicles to serve customers at minimum cost",
    "MIP",
    ["vrp", "vehicle routing", "delivery routing", "fleet routing"],
)
def _vrp(params: dict, solver: str) -> str:
    n_customers = params.get("n_customers", 5)
    n_vehicles = params.get("n_vehicles", 2)
    capacity = params.get("capacity", 30)
    dist = params.get("distances", None)
    demands = params.get("demands", None)

    d_str = str(demands) if demands else f"[0, 5, 8, 3, 7, 4][:{n_customers}+1]"

    return f"""\
from pyomo.environ import *
import random

model = ConcreteModel()
C = {n_customers}
K = {n_vehicles}
N = C + 1  # customers + depot
customers = range(1, N)
vehicles = range(K)
nodes = range(N)

demands = {d_str}
capacity = {capacity}

random.seed(42)
coords = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(N)]
dist = {{(i,j): ((coords[i][0]-coords[j][0])**2 + (coords[i][1]-coords[j][1])**2)**0.5
         for i in nodes for j in nodes if i != j}}

model.x = Var(nodes, nodes, vehicles, domain=Binary)
model.u = Var(nodes, domain=NonNegativeReals, bounds=(0, capacity))

# Minimize total distance
model.obj = Objective(
    expr=sum(dist[i,j] * model.x[i,j,k] for i in nodes for j in nodes for k in vehicles if i != j),
    sense=minimize)

# Each customer visited exactly once
model.visit = ConstraintList()
for j in customers:
    model.visit.add(
        sum(model.x[i,j,k] for i in nodes for k in vehicles if i != j) == 1)

# Flow conservation
model.flow = ConstraintList()
for h in nodes:
    for k in vehicles:
        model.flow.add(
            sum(model.x[i,h,k] for i in nodes if i != h) ==
            sum(model.x[h,j,k] for j in nodes if j != h))

# Vehicle starts and ends at depot
model.depot_start = ConstraintList()
for k in vehicles:
    model.depot_start.add(
        sum(model.x[0,j,k] for j in customers) == 1)

model.depot_end = ConstraintList()
for k in vehicles:
    model.depot_end.add(
        sum(model.x[i,0,k] for i in customers) == 1)

# Capacity (MTZ)
model.capacity_con = ConstraintList()
for i in customers:
    for j in customers:
        if i != j:
            model.capacity_con.add(
                model.u[i] - model.u[j] + capacity * (model.x.sum(i,j,'*')) <= capacity - demands[j])

solver = SolverFactory('{solver}')
result = solver.solve(model, tee=False)

print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))
print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))
print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))
print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))

print("ROUTES:")
for k in vehicles:
    route = []
    current = 0
    while True:
        next_nodes = [j for j in nodes if j != current and value(model.x[current,j,k]) > 0.5]
        if not next_nodes or next_nodes[0] == 0:
            route.append(0)
            break
        current = next_nodes[0]
        route.append(current)
    route_str = ' -> '.join(str(n) for n in route)
    print(f"  Vehicle {{k}}: {{route_str}}")
"""


# ── Tool spec and handler ──

TEMPLATES_TOOL_SPEC = {
    "name": "problem_templates",
    "description": (
        "List available OR problem templates or generate a model from a template. "
        "Templates provide reliable, tested Pyomo models for standard OR problems. "
        "Use 'list' to see all templates, 'generate' to create a model from a template."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["list", "generate", "match"],
                "description": "Operation: 'list' to show templates, 'generate' to create model, 'match' to find best template",
                "default": "list",
            },
            "template_name": {
                "type": "string",
                "description": "Template name (e.g., 'tsp', 'knapsack', 'facility_location')",
            },
            "description": {
                "type": "string",
                "description": "Problem description for 'match' operation",
            },
            "params": {
                "type": "object",
                "description": "Template parameters (e.g., {'n': 5, 'capacity': 50})",
                "default": {},
            },
            "solver": {
                "type": "string",
                "description": "Solver to use (default: highs)",
                "default": "highs",
            },
        },
    },
}


async def templates_handler(args: dict[str, Any], session=None) -> tuple[str, bool]:
    """Handler for problem_templates tool."""
    operation = args.get("operation", "list")

    if operation == "list":
        return list_templates(), False

    if operation == "match":
        desc = args.get("description", "")
        if not desc:
            return "Error: No description provided for matching", True
        matched = match_template(desc)
        if matched:
            tpl = TEMPLATES[matched]
            return (
                f"## Matched Template: {matched}\n\n"
                f"**Type**: {tpl['problem_type']}\n"
                f"**Description**: {tpl['description']}\n\n"
                f"Use `operation: 'generate'` with `template_name: '{matched}'` to create the model.",
                False,
            )
        return "No matching template found. Use `model_builder` for custom problems.", False

    if operation == "generate":
        name = args.get("template_name", "")
        if not name:
            return "Error: No template_name provided", True
        params = args.get("params", {})
        solver = args.get("solver") or (session.config.solver.default)
        filename = args.get("filename", "")

        try:
            code = generate_from_template(name, params, solver)
            workspace = get_workspace_dir(session)
            if filename:
                model_file = workspace / filename
            else:
                model_file = workspace / suggest_filename(workspace, f"model_{name}", ".py")
            model_file.write_text(code, encoding="utf-8")
            record_file(workspace, model_file.name, file_type="pyomo_model",
                        tool="problem_templates", note=f"Template: {name}")
            tpl = TEMPLATES[name]
            return (
                f"## Model Generated from Template: {name}\n\n"
                f"**Type**: {tpl['problem_type']}\n"
                f"**Description**: {tpl['description']}\n"
                f"**Model file**: {model_file}\n\n"
                f"Now use `solve_job` with model_path='{model_file}' to solve.",
                False,
            )
        except ValueError as e:
            return str(e), True

    return f"Unknown operation: {operation}", True
