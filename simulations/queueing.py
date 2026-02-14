# ABOUTME: M/M/c queueing simulation (multi-server queue)
# ABOUTME: Models customer arrivals, waiting, and service with configurable servers

import simpy
import random
import numpy as np
from typing import Callable, Optional

from simulations.base import BaseSimulation, EventType
from simulations.registry import SimulationRegistry


@SimulationRegistry.register
class QueueingSimulation(BaseSimulation):
    """
    Multi-server queueing system simulation (M/M/c queue).
    Models customers arriving, waiting in queue, and being served.
    """

    name = "queueing"
    description = "Multi-server queueing system (M/M/c queue) - models arrivals, waiting, and service"

    def get_parameter_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "n_servers": {
                    "type": "integer",
                    "default": 1,
                    "minimum": 1,
                    "description": "Number of parallel service stations"
                },
                "arrival_rate": {
                    "type": "number",
                    "default": 5.0,
                    "minimum": 0.001,
                    "description": "Customer arrival rate per time unit"
                },
                "service_time": {
                    "type": "number",
                    "default": 3.0,
                    "minimum": 0.001,
                    "description": "Average service time per customer"
                },
                "sim_time": {
                    "type": "integer",
                    "default": 1440,
                    "minimum": 1,
                    "description": "Total simulation time"
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
                "total_customers": {
                    "type": "integer",
                    "description": "Total customers served"
                },
                "avg_wait_time": {
                    "type": "number",
                    "description": "Average time spent waiting before service"
                },
                "avg_system_time": {
                    "type": "number",
                    "description": "Average total time in system (wait + service)"
                },
                "max_wait_time": {
                    "type": "number",
                    "description": "Maximum wait time observed"
                },
                "server_utilization": {
                    "type": "number",
                    "description": "Fraction of time servers were busy"
                }
            }
        }

    def run(
        self,
        params: dict,
        callback: Optional[Callable] = None
    ) -> dict:
        validated = self.validate_params(params)

        n_servers = validated["n_servers"]
        arrival_rate = validated["arrival_rate"]
        service_time = validated["service_time"]
        sim_time = validated["sim_time"]
        random_seed = validated["random_seed"]

        # Metrics collection
        wait_times = []
        system_times = []
        customers_served = 0
        total_busy_time = 0

        def customer(env, name, server):
            nonlocal customers_served, total_busy_time
            arrival_time = env.now

            self.emit_event(callback, EventType.ENTITY_ARRIVAL, env.now, {
                "entity": name,
                "queue_length": len(server.queue)
            })

            with server.request() as request:
                yield request
                start_service = env.now
                wait_time = start_service - arrival_time
                wait_times.append(wait_time)

                self.emit_event(callback, EventType.ENTITY_START_SERVICE, env.now, {
                    "entity": name,
                    "wait_time": wait_time
                })

                yield env.timeout(service_time)

                end_time = env.now
                system_time = end_time - arrival_time
                system_times.append(system_time)
                customers_served += 1
                total_busy_time += service_time

                self.emit_event(callback, EventType.ENTITY_END_SERVICE, env.now, {
                    "entity": name,
                    "system_time": system_time
                })

        def customer_generator(env, server):
            i = 0
            while True:
                yield env.timeout(random.expovariate(arrival_rate))
                env.process(customer(env, f"Customer_{i}", server))
                i += 1

        # Set up environment
        random.seed(random_seed)
        env = simpy.Environment()
        server = simpy.Resource(env, capacity=n_servers)

        self.emit_event(callback, EventType.START, 0, {
            "n_servers": n_servers,
            "arrival_rate": arrival_rate,
            "service_time": service_time
        })

        env.process(customer_generator(env, server))
        env.run(until=sim_time)

        # Calculate metrics
        avg_wait = round(np.mean(wait_times), 2) if wait_times else 0
        avg_system = round(np.mean(system_times), 2) if system_times else 0
        max_wait = round(max(wait_times), 2) if wait_times else 0
        utilization = round(total_busy_time / (sim_time * n_servers), 4) if sim_time > 0 else 0

        result = {
            "total_customers": customers_served,
            "avg_wait_time": avg_wait,
            "avg_system_time": avg_system,
            "max_wait_time": max_wait,
            "server_utilization": utilization
        }

        self.emit_event(callback, EventType.END, sim_time, result)

        return result
