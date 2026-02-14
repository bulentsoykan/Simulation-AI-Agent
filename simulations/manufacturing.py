# ABOUTME: Manufacturing production line simulation with multiple stations
# ABOUTME: Models work-in-progress flow through stations with buffers and processing times

import simpy
import random
import numpy as np
from typing import Callable, Optional
from dataclasses import dataclass

from simulations.base import BaseSimulation, EventType
from simulations.registry import SimulationRegistry


@dataclass
class Station:
    """Represents a production station"""
    name: str
    processing_time: float
    buffer_size: int


@SimulationRegistry.register
class ManufacturingSimulation(BaseSimulation):
    """
    Production line simulation with multiple stations.
    Models work items flowing through stations with buffers.
    """

    name = "manufacturing"
    description = "Production line with stations, buffers, and processing times"

    def get_parameter_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "stations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["Cutting", "Assembly", "QC", "Packaging"],
                    "description": "Names of production stations in order"
                },
                "processing_times": {
                    "type": "array",
                    "items": {"type": "number"},
                    "default": [2.0, 5.0, 1.5, 2.0],
                    "description": "Processing time at each station"
                },
                "buffer_sizes": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "default": [10, 10, 10, 10],
                    "description": "Buffer capacity before each station"
                },
                "arrival_rate": {
                    "type": "number",
                    "default": 0.3,
                    "minimum": 0.001,
                    "description": "Raw material arrival rate"
                },
                "sim_time": {
                    "type": "integer",
                    "default": 480,
                    "minimum": 1,
                    "description": "Simulation time (e.g., 480 = 8 hour shift)"
                },
                "random_seed": {
                    "type": "integer",
                    "default": 42,
                    "description": "Seed for reproducibility"
                }
            },
            "required": []
        }

    def get_metrics_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "throughput": {
                    "type": "integer",
                    "description": "Total items completed"
                },
                "avg_cycle_time": {
                    "type": "number",
                    "description": "Average time from start to finish"
                },
                "wip": {
                    "type": "number",
                    "description": "Average work-in-progress"
                },
                "station_utilization": {
                    "type": "object",
                    "description": "Utilization per station"
                },
                "bottleneck_station": {
                    "type": "string",
                    "description": "Station with highest utilization"
                }
            }
        }

    def run(
        self,
        params: dict,
        callback: Optional[Callable] = None
    ) -> dict:
        validated = self.validate_params(params)

        station_names = validated["stations"]
        processing_times = validated["processing_times"]
        buffer_sizes = validated["buffer_sizes"]
        arrival_rate = validated["arrival_rate"]
        sim_time = validated["sim_time"]
        random_seed = validated["random_seed"]

        # Validate array lengths match
        n_stations = len(station_names)
        if len(processing_times) != n_stations:
            processing_times = processing_times[:n_stations] + [2.0] * (n_stations - len(processing_times))
        if len(buffer_sizes) != n_stations:
            buffer_sizes = buffer_sizes[:n_stations] + [10] * (n_stations - len(buffer_sizes))

        # Metrics collection
        cycle_times = []
        completed_items = 0
        station_busy_time = {name: 0 for name in station_names}
        wip_samples = []

        # Track items in system
        items_in_system = 0

        def work_item(env, item_id, stations, buffers):
            nonlocal completed_items, items_in_system
            items_in_system += 1
            start_time = env.now

            self.emit_event(callback, EventType.ENTITY_ARRIVAL, env.now, {
                "item": f"Item_{item_id}",
                "station": station_names[0]
            })

            for i, (station, buffer) in enumerate(zip(stations, buffers)):
                station_name = station_names[i]
                proc_time = processing_times[i]

                # Wait for buffer space (if not first station)
                if i > 0:
                    yield buffer.get(1)

                # Process at station
                with station.request() as req:
                    yield req

                    self.emit_event(callback, EventType.ENTITY_START_SERVICE, env.now, {
                        "item": f"Item_{item_id}",
                        "station": station_name
                    })

                    # Add variability to processing time
                    actual_time = random.gauss(proc_time, proc_time * 0.1)
                    actual_time = max(0.1, actual_time)
                    yield env.timeout(actual_time)

                    station_busy_time[station_name] += actual_time

                    self.emit_event(callback, EventType.ENTITY_END_SERVICE, env.now, {
                        "item": f"Item_{item_id}",
                        "station": station_name
                    })

                # Put into next buffer (if not last station)
                if i < len(stations) - 1:
                    yield buffers[i + 1].put(1)

            # Item completed
            end_time = env.now
            cycle_times.append(end_time - start_time)
            completed_items += 1
            items_in_system -= 1

            self.emit_event(callback, EventType.ENTITY_DEPARTURE, env.now, {
                "item": f"Item_{item_id}",
                "cycle_time": end_time - start_time
            })

        def item_generator(env, stations, buffers):
            item_id = 0
            while True:
                yield env.timeout(random.expovariate(arrival_rate))
                env.process(work_item(env, item_id, stations, buffers))
                item_id += 1

        def wip_monitor(env):
            while True:
                wip_samples.append(items_in_system)
                yield env.timeout(10)  # Sample every 10 time units

        # Set up environment
        random.seed(random_seed)
        env = simpy.Environment()

        # Create stations (resources) and buffers (containers)
        stations = [simpy.Resource(env, capacity=1) for _ in station_names]
        buffers = [simpy.Container(env, capacity=size, init=0) for size in buffer_sizes]

        self.emit_event(callback, EventType.START, 0, {
            "stations": station_names,
            "processing_times": processing_times,
            "buffer_sizes": buffer_sizes
        })

        env.process(item_generator(env, stations, buffers))
        env.process(wip_monitor(env))
        env.run(until=sim_time)

        # Calculate metrics
        avg_cycle = round(np.mean(cycle_times), 2) if cycle_times else 0
        avg_wip = round(np.mean(wip_samples), 2) if wip_samples else 0

        utilization = {}
        for name in station_names:
            utilization[name] = round(station_busy_time[name] / sim_time, 4)

        bottleneck = max(utilization, key=utilization.get) if utilization else ""

        result = {
            "throughput": completed_items,
            "avg_cycle_time": avg_cycle,
            "wip": avg_wip,
            "station_utilization": utilization,
            "bottleneck_station": bottleneck
        }

        self.emit_event(callback, EventType.END, sim_time, result)

        return result
