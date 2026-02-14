# ABOUTME: Central registry for simulation plugins
# ABOUTME: Handles registration, discovery, and instantiation of simulation types

from typing import Type
from simulations.base import BaseSimulation


class SimulationRegistry:
    """
    Registry for simulation plugins.

    Usage:
        # Register a simulation
        @SimulationRegistry.register
        class MySimulation(BaseSimulation):
            name = "my_simulation"
            ...

        # Or register manually
        SimulationRegistry.register(MySimulation)

        # Get a simulation instance
        sim = SimulationRegistry.get("my_simulation")

        # List all registered simulations
        all_sims = SimulationRegistry.list_all()
    """

    _simulations: dict[str, Type[BaseSimulation]] = {}

    @classmethod
    def register(cls, sim_class: Type[BaseSimulation]) -> Type[BaseSimulation]:
        """
        Register a simulation class.
        Can be used as a decorator or called directly.
        """
        if not sim_class.name:
            raise ValueError(f"Simulation class {sim_class.__name__} must have a 'name' attribute")

        cls._simulations[sim_class.name] = sim_class
        return sim_class

    @classmethod
    def get(cls, name: str) -> BaseSimulation:
        """Get an instance of a registered simulation by name"""
        if name not in cls._simulations:
            available = ", ".join(cls._simulations.keys())
            raise KeyError(f"Simulation '{name}' not found. Available: {available}")

        return cls._simulations[name]()

    @classmethod
    def get_class(cls, name: str) -> Type[BaseSimulation]:
        """Get the class (not instance) of a registered simulation"""
        if name not in cls._simulations:
            available = ", ".join(cls._simulations.keys())
            raise KeyError(f"Simulation '{name}' not found. Available: {available}")

        return cls._simulations[name]

    @classmethod
    def list_all(cls) -> list[dict]:
        """List all registered simulations with their metadata"""
        result = []
        for sim_class in cls._simulations.values():
            instance = sim_class()
            result.append({
                "name": sim_class.name,
                "description": sim_class.description,
                "parameters": instance.get_parameter_schema(),
                "metrics": instance.get_metrics_schema()
            })
        return result

    @classmethod
    def list_names(cls) -> list[str]:
        """List names of all registered simulations"""
        return list(cls._simulations.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a simulation is registered"""
        return name in cls._simulations

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (useful for testing)"""
        cls._simulations = {}
