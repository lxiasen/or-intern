"""Shared test fixtures for OR-Intern."""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory(prefix="or_intern_test_") as d:
        yield Path(d)


@pytest.fixture
def sample_lp_problem():
    """Standard LP test problem."""
    return {
        "description": "maximize 3x + 2y subject to x + y <= 10, x >= 0, y >= 0",
        "optimal_x": 10.0,
        "optimal_y": 0.0,
        "optimal_obj": 30.0,
    }


@pytest.fixture
def sample_model_code():
    """Pre-built Pyomo model code for testing."""
    return """from pyomo.environ import *

model = ConcreteModel()
model.x = Var(domain=NonNegativeReals)
model.y = Var(domain=NonNegativeReals)
model.obj = Objective(expr=3*model.x + 2*model.y, sense=maximize)
model.c1 = Constraint(expr=model.x + model.y <= 10)

solver = SolverFactory('highs')
result = solver.solve(model, tee=False)
print("STATUS:", result.solver.termination_condition)
print("OBJECTIVE:", value(model.obj))
print("  x =", value(model.x))
print("  y =", value(model.y))
"""


@pytest.fixture
def model_file(temp_dir, sample_model_code):
    """Create a temporary model file for solve tests."""
    path = temp_dir / "test_model.py"
    path.write_text(sample_model_code, encoding="utf-8")
    return str(path)
