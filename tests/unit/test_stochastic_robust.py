"""Unit tests for stochastic and robust optimization tools."""

import pytest
from pathlib import Path


class TestUncertaintyModeler:
    """Test uncertainty modeling."""

    def test_define_parameter_normal(self):
        from agent.tools.uncertainty_modeler import UncertaintyModeler
        modeler = UncertaintyModeler()
        param = modeler.define_parameter("demand", "normal", mean=100, std=20)
        assert param.name == "demand"
        assert param.distribution == "normal"

    def test_define_parameter_uniform(self):
        from agent.tools.uncertainty_modeler import UncertaintyModeler
        modeler = UncertaintyModeler()
        param = modeler.define_parameter("price", "uniform", low=10, high=20)
        assert param.name == "price"
        assert param.distribution == "uniform"

    def test_generate_scenarios_normal(self):
        from agent.tools.uncertainty_modeler import UncertaintyModeler
        modeler = UncertaintyModeler()
        modeler.define_parameter("demand", "normal", mean=100, std=20)
        scenarios = modeler.generate_scenarios("demand", 50)
        assert len(scenarios) == 50
        assert 80 < scenarios.mean() < 120

    def test_generate_scenarios_uniform(self):
        from agent.tools.uncertainty_modeler import UncertaintyModeler
        modeler = UncertaintyModeler()
        modeler.define_parameter("price", "uniform", low=10, high=20)
        scenarios = modeler.generate_scenarios("price", 100)
        assert len(scenarios) == 100
        assert scenarios.min() >= 10
        assert scenarios.max() <= 20

    def test_generate_scenario_matrix(self):
        from agent.tools.uncertainty_modeler import UncertaintyModeler
        modeler = UncertaintyModeler()
        modeler.define_parameter("demand", "normal", mean=100, std=20)
        modeler.define_parameter("price", "uniform", low=10, high=20)
        matrix = modeler.generate_scenario_matrix(50)
        assert "demand" in matrix
        assert "price" in matrix
        assert len(matrix["demand"]) == 50

    def test_get_bounds_uniform(self):
        from agent.tools.uncertainty_modeler import UncertaintyModeler
        modeler = UncertaintyModeler()
        modeler.define_parameter("x", "uniform", low=10, high=20)
        low, high = modeler.get_bounds("x")
        assert low == 10
        assert high == 20

    def test_get_bounds_normal(self):
        from agent.tools.uncertainty_modeler import UncertaintyModeler
        modeler = UncertaintyModeler()
        modeler.define_parameter("x", "normal", mean=100, std=10)
        low, high = modeler.get_bounds("x")
        assert low == 70
        assert high == 130


class TestParseUncertainty:
    """Test uncertainty description parsing."""

    def test_parse_interval(self):
        from agent.tools.uncertainty_modeler import parse_uncertainty_description
        result = parse_uncertainty_description("demand in [100, 200]")
        assert "demand" in result
        assert result["demand"]["distribution"] == "uniform"
        assert result["demand"]["low"] == 100
        assert result["demand"]["high"] == 200

    def test_parse_normal(self):
        from agent.tools.uncertainty_modeler import parse_uncertainty_description
        result = parse_uncertainty_description("demand ~ N(100, 20)")
        assert "demand" in result
        assert result["demand"]["distribution"] == "normal"
        assert result["demand"]["mean"] == 100


class TestStochasticBuilder:
    """Test stochastic programming builder."""

    def test_spec_has_required_fields(self):
        from agent.tools.stochastic_builder import STOCHASTIC_BUILDER_TOOL_SPEC
        spec = STOCHASTIC_BUILDER_TOOL_SPEC
        assert spec["name"] == "stochastic_builder"
        assert "parameters" in spec

    def test_generate_model(self):
        from agent.tools.stochastic_builder import generate_stochastic_model
        code = generate_stochastic_model(
            "Minimize cost, demand in [100, 200] is uncertain",
            n_scenarios=10,
        )
        assert "ConcreteModel" in code
        assert "scenarios" in code
        assert "Objective" in code

    @pytest.mark.asyncio
    async def test_handler_empty_description(self, session):
        from agent.tools.stochastic_builder import stochastic_builder_handler
        output, is_error = await stochastic_builder_handler({"description": ""}, session=session)
        assert is_error


class TestRobustBuilder:
    """Test robust optimization builder."""

    def test_spec_has_required_fields(self):
        from agent.tools.robust_builder import ROBUST_BUILDER_TOOL_SPEC
        spec = ROBUST_BUILDER_TOOL_SPEC
        assert spec["name"] == "robust_builder"
        assert "parameters" in spec

    def test_detect_box_uncertainty(self):
        from agent.tools.robust_builder import _detect_uncertainty_set_type
        assert _detect_uncertainty_set_type("demand in [100, 200]") == "box"

    def test_detect_ellipsoidal_uncertainty(self):
        from agent.tools.robust_builder import _detect_uncertainty_set_type
        assert _detect_uncertainty_set_type("with ellipsoidal uncertainty") == "ellipsoidal"

    def test_extract_bounds(self):
        from agent.tools.robust_builder import _extract_bounds
        bounds = _extract_bounds("demand in [100, 200], price in [10, 20]")
        assert "demand" in bounds
        assert bounds["demand"] == (100, 200)

    def test_generate_box_model(self):
        from agent.tools.robust_builder import generate_robust_model
        code = generate_robust_model(
            "Minimize cost, demand in [100, 200], robust optimization"
        )
        assert "ConcreteModel" in code
        assert "Objective" in code

    def test_generate_ellipsoidal_model(self):
        from agent.tools.robust_builder import generate_robust_model
        code = generate_robust_model(
            "Minimize cost, ellipsoidal uncertainty",
            gamma=2.0,
        )
        assert "ConcreteModel" in code
        assert "Gamma" in code