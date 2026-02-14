# ABOUTME: Vehicle routing simulation with capacity constraints
# ABOUTME: Models delivery vehicles serving customer locations with demands

import simpy
import random
import numpy as np
from typing import Callable, Optional
from dataclasses import dataclass
import math

from simulations.base import BaseSimulation, EventType
from simulations.registry import SimulationRegistry


@dataclass
class Location:
    """Represents a customer location"""
    id: int
    x: float
    y: float
    demand: int


@SimulationRegistry.register
class LogisticsSimulation(BaseSimulation):
    """
    Vehicle routing simulation with capacity constraints.
    Models a fleet of vehicles serving customer locations.
    """

    name = "logistics"
    description = "Capacitated vehicle routing with multiple vehicles and customer locations"

    def get_parameter_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "num_vehicles": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 1,
                    "description": "Number of delivery vehicles"
                },
                "vehicle_capacity": {
                    "type": "integer",
                    "default": 100,
                    "minimum": 1,
                    "description": "Capacity per vehicle"
                },
                "vehicle_speed": {
                    "type": "number",
                    "default": 1.0,
                    "minimum": 0.1,
                    "description": "Vehicle travel speed (distance per time unit)"
                },
                "num_customers": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "description": "Number of customer locations"
                },
                "area_size": {
                    "type": "number",
                    "default": 100.0,
                    "minimum": 1,
                    "description": "Size of delivery area (area_size x area_size)"
                },
                "min_demand": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "description": "Minimum demand per customer"
                },
                "max_demand": {
                    "type": "integer",
                    "default": 30,
                    "minimum": 1,
                    "description": "Maximum demand per customer"
                },
                "service_time": {
                    "type": "number",
                    "default": 5.0,
                    "minimum": 0,
                    "description": "Time to serve each customer"
                },
                "sim_time": {
                    "type": "integer",
                    "default": 480,
                    "minimum": 1,
                    "description": "Available time (e.g., 480 = 8 hour shift)"
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
                "customers_served": {
                    "type": "integer",
                    "description": "Number of customers served"
                },
                "customers_unserved": {
                    "type": "integer",
                    "description": "Number of customers not served"
                },
                "total_demand": {
                    "type": "integer",
                    "description": "Total demand across all customers"
                },
                "demand_fulfilled": {
                    "type": "integer",
                    "description": "Total demand fulfilled"
                },
                "total_distance": {
                    "type": "number",
                    "description": "Total distance traveled by all vehicles"
                },
                "vehicle_utilization": {
                    "type": "object",
                    "description": "Utilization per vehicle (time active / total time)"
                },
                "avg_delivery_time": {
                    "type": "number",
                    "description": "Average time from start to delivery completion"
                }
            }
        }

    def _distance(self, loc1: Location, loc2: Location) -> float:
        """Euclidean distance between two locations"""
        return math.sqrt((loc1.x - loc2.x) ** 2 + (loc1.y - loc2.y) ** 2)

    def _nearest_unvisited(
        self,
        current: Location,
        unvisited: list[Location],
        remaining_capacity: int
    ) -> Optional[Location]:
        """Find nearest unvisited customer that fits in remaining capacity"""
        candidates = [loc for loc in unvisited if loc.demand <= remaining_capacity]
        if not candidates:
            return None

        return min(candidates, key=lambda loc: self._distance(current, loc))

    def run(
        self,
        params: dict,
        callback: Optional[Callable] = None
    ) -> dict:
        validated = self.validate_params(params)

        num_vehicles = validated["num_vehicles"]
        vehicle_capacity = validated["vehicle_capacity"]
        vehicle_speed = validated["vehicle_speed"]
        num_customers = validated["num_customers"]
        area_size = validated["area_size"]
        min_demand = validated["min_demand"]
        max_demand = validated["max_demand"]
        service_time = validated["service_time"]
        sim_time = validated["sim_time"]
        random_seed = validated["random_seed"]

        random.seed(random_seed)

        # Generate depot and customer locations
        depot = Location(id=0, x=area_size / 2, y=area_size / 2, demand=0)

        customers = []
        for i in range(num_customers):
            loc = Location(
                id=i + 1,
                x=random.uniform(0, area_size),
                y=random.uniform(0, area_size),
                demand=random.randint(min_demand, max_demand)
            )
            customers.append(loc)

        # Metrics
        customers_served = 0
        total_demand = sum(c.demand for c in customers)
        demand_fulfilled = 0
        total_distance = 0
        vehicle_active_time = {f"Vehicle_{i}": 0 for i in range(num_vehicles)}
        delivery_times = []

        # Track unvisited customers
        unvisited = customers.copy()

        def vehicle_process(env, vehicle_id, vehicle_name):
            nonlocal customers_served, demand_fulfilled, total_distance, unvisited

            while unvisited:
                current = depot
                remaining_capacity = vehicle_capacity
                route_distance = 0
                route_start_time = env.now

                self.emit_event(callback, EventType.STATE_CHANGE, env.now, {
                    "event": "vehicle_depart",
                    "vehicle": vehicle_name,
                    "capacity": remaining_capacity
                })

                # Build route using nearest neighbor
                while True:
                    next_customer = self._nearest_unvisited(current, unvisited, remaining_capacity)
                    if next_customer is None:
                        break

                    # Travel to customer
                    dist = self._distance(current, next_customer)
                    travel_time = dist / vehicle_speed

                    # Check if we have time
                    if env.now + travel_time + service_time > sim_time:
                        break

                    yield env.timeout(travel_time)
                    route_distance += dist

                    self.emit_event(callback, EventType.ENTITY_START_SERVICE, env.now, {
                        "vehicle": vehicle_name,
                        "customer": next_customer.id,
                        "demand": next_customer.demand
                    })

                    # Serve customer
                    yield env.timeout(service_time)

                    # Update metrics
                    remaining_capacity -= next_customer.demand
                    demand_fulfilled += next_customer.demand
                    customers_served += 1
                    unvisited.remove(next_customer)
                    delivery_times.append(env.now - route_start_time)

                    self.emit_event(callback, EventType.ENTITY_END_SERVICE, env.now, {
                        "vehicle": vehicle_name,
                        "customer": next_customer.id,
                        "remaining_capacity": remaining_capacity
                    })

                    current = next_customer

                # Return to depot
                dist = self._distance(current, depot)
                travel_time = dist / vehicle_speed

                if env.now + travel_time <= sim_time:
                    yield env.timeout(travel_time)
                    route_distance += dist

                total_distance += route_distance
                vehicle_active_time[vehicle_name] += env.now - route_start_time

                self.emit_event(callback, EventType.STATE_CHANGE, env.now, {
                    "event": "vehicle_return",
                    "vehicle": vehicle_name,
                    "route_distance": route_distance
                })

                # Check if more customers remain and we have time
                if not unvisited or env.now >= sim_time:
                    break

        # Set up environment
        env = simpy.Environment()

        self.emit_event(callback, EventType.START, 0, {
            "num_vehicles": num_vehicles,
            "num_customers": num_customers,
            "total_demand": total_demand
        })

        # Start all vehicles
        for i in range(num_vehicles):
            env.process(vehicle_process(env, i, f"Vehicle_{i}"))

        env.run(until=sim_time)

        # Calculate metrics
        customers_unserved = len(unvisited)

        utilization = {}
        for vehicle_name, active_time in vehicle_active_time.items():
            utilization[vehicle_name] = round(active_time / sim_time, 4)

        avg_delivery = round(np.mean(delivery_times), 2) if delivery_times else 0

        result = {
            "customers_served": customers_served,
            "customers_unserved": customers_unserved,
            "total_demand": total_demand,
            "demand_fulfilled": demand_fulfilled,
            "total_distance": round(total_distance, 2),
            "vehicle_utilization": utilization,
            "avg_delivery_time": avg_delivery
        }

        self.emit_event(callback, EventType.END, sim_time, result)

        return result
