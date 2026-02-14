# ABOUTME: Simulation plugin package - provides extensible simulation framework
# ABOUTME: Exports BaseSimulation, SimulationRegistry, and built-in simulation types

from simulations.base import BaseSimulation, SimulationEvent, EventType
from simulations.registry import SimulationRegistry

# Import all built-in simulations to register them
from simulations.queueing import QueueingSimulation
from simulations.manufacturing import ManufacturingSimulation
from simulations.inventory import InventorySimulation
from simulations.logistics import LogisticsSimulation

__all__ = [
    "BaseSimulation",
    "SimulationEvent",
    "EventType",
    "SimulationRegistry",
    "QueueingSimulation",
    "ManufacturingSimulation",
    "InventorySimulation",
    "LogisticsSimulation",
]
