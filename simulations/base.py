# ABOUTME: Abstract base class for all simulation types
# ABOUTME: Defines the interface that all simulation plugins must implement

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional
from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    """Types of events that simulations can emit"""
    START = "start"
    PROGRESS = "progress"
    ENTITY_ARRIVAL = "entity_arrival"
    ENTITY_START_SERVICE = "entity_start_service"
    ENTITY_END_SERVICE = "entity_end_service"
    ENTITY_DEPARTURE = "entity_departure"
    STATE_CHANGE = "state_change"
    END = "end"


@dataclass
class SimulationEvent:
    """Event emitted during simulation execution"""
    event_type: EventType
    time: float
    data: dict


class BaseSimulation(ABC):
    """
    Abstract base class for all simulation types.

    To create a new simulation type:
    1. Subclass BaseSimulation
    2. Set name and description class attributes
    3. Implement get_parameter_schema(), get_metrics_schema(), and run()
    4. Register with SimulationRegistry.register(YourSimulation)
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def get_parameter_schema(self) -> dict:
        """
        Returns JSON Schema for simulation parameters.

        Example:
            {
                "type": "object",
                "properties": {
                    "n_servers": {"type": "integer", "default": 1, "minimum": 1},
                    "arrival_rate": {"type": "number", "default": 5.0, "minimum": 0}
                },
                "required": []
            }
        """
        pass

    @abstractmethod
    def get_metrics_schema(self) -> dict:
        """
        Returns schema describing output metrics.

        Example:
            {
                "type": "object",
                "properties": {
                    "total_customers": {"type": "integer", "description": "Total customers served"},
                    "avg_wait_time": {"type": "number", "description": "Average wait time"}
                }
            }
        """
        pass

    @abstractmethod
    def run(
        self,
        params: dict,
        callback: Optional[Callable[[SimulationEvent], None]] = None
    ) -> dict:
        """
        Runs the simulation with given parameters.

        Args:
            params: Simulation parameters matching get_parameter_schema()
            callback: Optional callback for real-time event streaming

        Returns:
            dict containing metrics matching get_metrics_schema()
        """
        pass

    def validate_params(self, params: dict) -> dict:
        """
        Validates and fills in default values for parameters.
        Returns validated params dict.
        """
        schema = self.get_parameter_schema()
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        validated = {}

        for key, prop_schema in properties.items():
            if key in params:
                validated[key] = params[key]
            elif "default" in prop_schema:
                validated[key] = prop_schema["default"]
            elif key in required:
                raise ValueError(f"Missing required parameter: {key}")

        return validated

    def emit_event(
        self,
        callback: Optional[Callable[[SimulationEvent], None]],
        event_type: EventType,
        time: float,
        data: dict
    ) -> None:
        """Helper to emit an event if callback is provided"""
        if callback:
            event = SimulationEvent(event_type=event_type, time=time, data=data)
            callback(event)
