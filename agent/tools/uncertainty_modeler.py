"""Uncertainty modeler for OR-Intern v1.0.

Defines uncertainty sets and generates scenarios for stochastic/robust optimization.
Supports: normal, uniform, discrete distributions, and box/ellipsoidal uncertainty sets.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class UncertaintySet:
    """Uncertainty set definition for robust optimization."""
    name: str
    set_type: str  # box, ellipsoidal, polyhedral, discrete
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class UncertainParameter:
    """Definition of an uncertain parameter."""
    name: str
    distribution: str  # normal, uniform, discrete, custom
    parameters: dict[str, Any] = field(default_factory=dict)
    correlation: Optional[np.ndarray] = None


class UncertaintyModeler:
    """Uncertainty modeling for stochastic and robust optimization."""

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)
        self.uncertain_params: dict[str, UncertainParameter] = {}
        self.uncertainty_sets: dict[str, UncertaintySet] = {}

    def define_parameter(
        self,
        name: str,
        distribution: str,
        **params,
    ) -> UncertainParameter:
        """Define an uncertain parameter.

        Args:
            name: Parameter name
            distribution: Distribution type (normal, uniform, discrete)
            **params: Distribution parameters

        Returns:
            UncertainParameter object
        """
        param = UncertainParameter(
            name=name,
            distribution=distribution,
            parameters=params,
        )
        self.uncertain_params[name] = param
        return param

    def define_uncertainty_set(
        self,
        name: str,
        set_type: str,
        **params,
    ) -> UncertaintySet:
        """Define an uncertainty set for robust optimization.

        Args:
            name: Set name
            set_type: Set type (box, ellipsoidal, polyhedral)
            **params: Set parameters (e.g., center, radius, bounds)

        Returns:
            UncertaintySet object
        """
        uset = UncertaintySet(
            name=name,
            set_type=set_type,
            parameters=params,
        )
        self.uncertainty_sets[name] = uset
        return uset

    def generate_scenarios(
        self,
        param_name: str,
        n_scenarios: int,
        method: str = "monte_carlo",
    ) -> np.ndarray:
        """Generate scenarios for an uncertain parameter.

        Args:
            param_name: Parameter name
            n_scenarios: Number of scenarios to generate
            method: Sampling method (monte_carlo, latin_hypercube)

        Returns:
            Array of scenario values
        """
        param = self.uncertain_params.get(param_name)
        if param is None:
            raise ValueError(f"Unknown parameter: {param_name}")

        if method == "latin_hypercube":
            return self._latin_hypercube_sample(param, n_scenarios)
        return self._monte_carlo_sample(param, n_scenarios)

    def _monte_carlo_sample(
        self,
        param: UncertainParameter,
        n_scenarios: int,
    ) -> np.ndarray:
        """Monte Carlo sampling."""
        if param.distribution == "normal":
            return self.rng.normal(
                loc=param.parameters.get("mean", 0),
                scale=param.parameters.get("std", 1),
                size=n_scenarios,
            )
        elif param.distribution == "uniform":
            return self.rng.uniform(
                low=param.parameters.get("low", 0),
                high=param.parameters.get("high", 1),
                size=n_scenarios,
            )
        elif param.distribution == "discrete":
            values = np.array(param.parameters.get("values", [0]))
            probs = param.parameters.get("probabilities", None)
            return self.rng.choice(values, size=n_scenarios, p=probs)
        else:
            raise ValueError(f"Unknown distribution: {param.distribution}")

    def _latin_hypercube_sample(
        self,
        param: UncertainParameter,
        n_scenarios: int,
    ) -> np.ndarray:
        """Latin Hypercube Sampling for better coverage."""
        if param.distribution == "uniform":
            low = param.parameters.get("low", 0)
            high = param.parameters.get("high", 1)
            return low + (high - low) * self._lhs_uniform(n_scenarios)
        elif param.distribution == "normal":
            mean = param.parameters.get("mean", 0)
            std = param.parameters.get("std", 1)
            from scipy.stats import norm
            return mean + std * norm.ppf(self._lhs_uniform(n_scenarios))
        else:
            return self._monte_carlo_sample(param, n_scenarios)

    def _lhs_uniform(self, n: int) -> np.ndarray:
        """Generate uniform LHS samples in [0, 1]."""
        intervals = np.linspace(0, 1, n + 1)
        samples = self.rng.uniform(intervals[:-1], intervals[1:])
        self.rng.shuffle(samples)
        return samples

    def generate_scenario_matrix(
        self,
        n_scenarios: int,
        method: str = "monte_carlo",
    ) -> dict[str, np.ndarray]:
        """Generate scenarios for all defined uncertain parameters.

        Args:
            n_scenarios: Number of scenarios
            method: Sampling method

        Returns:
            Dict mapping parameter names to scenario arrays
        """
        scenarios = {}
        for name in self.uncertain_params:
            scenarios[name] = self.generate_scenarios(name, n_scenarios, method)
        return scenarios

    def get_bounds(self, param_name: str) -> tuple[float, float]:
        """Get bounds for an uncertain parameter.

        Returns:
            (lower_bound, upper_bound) tuple
        """
        param = self.uncertain_params.get(param_name)
        if param is None:
            raise ValueError(f"Unknown parameter: {param_name}")

        if param.distribution == "uniform":
            return param.parameters.get("low", 0), param.parameters.get("high", 1)
        elif param.distribution == "normal":
            mean = param.parameters.get("mean", 0)
            std = param.parameters.get("std", 1)
            return mean - 3 * std, mean + 3 * std
        elif param.distribution == "discrete":
            values = param.parameters.get("values", [0])
            return min(values), max(values)
        else:
            raise ValueError(f"Cannot compute bounds for distribution: {param.distribution}")


def parse_uncertainty_description(description: str) -> dict[str, Any]:
    """Parse uncertainty description from natural language.

    Args:
        description: Natural language description of uncertainty

    Returns:
        Dict with uncertainty parameters
    """
    import re

    result = {}

    interval_pattern = re.compile(
        r"(\w+)\s*(?:in|∈)\s*\[([0-9.]+),\s*([0-9.]+)\]"
    )
    for match in interval_pattern.finditer(description):
        name = match.group(1)
        low = float(match.group(2))
        high = float(match.group(3))
        result[name] = {
            "distribution": "uniform",
            "low": low,
            "high": high,
        }

    normal_pattern = re.compile(
        r"(\w+)\s*(?:~|follows|is)\s*(?:N|Normal)\s*\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)"
    )
    for match in normal_pattern.finditer(description):
        name = match.group(1)
        mean = float(match.group(2))
        std = float(match.group(3))
        result[name] = {
            "distribution": "normal",
            "mean": mean,
            "std": std,
        }

    return result
