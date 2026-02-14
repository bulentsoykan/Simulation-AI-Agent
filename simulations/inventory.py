# ABOUTME: Inventory management simulation with (s,S) reorder policy
# ABOUTME: Models demand, stockouts, and replenishment with lead times

import simpy
import random
import numpy as np
from typing import Callable, Optional

from simulations.base import BaseSimulation, EventType
from simulations.registry import SimulationRegistry


@SimulationRegistry.register
class InventorySimulation(BaseSimulation):
    """
    Inventory management simulation with (s,S) policy.
    When inventory drops to s, order up to S.
    """

    name = "inventory"
    description = "Inventory management with (s,S) reorder policy and lead times"

    def get_parameter_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "reorder_point": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 0,
                    "description": "Inventory level (s) that triggers reorder"
                },
                "order_up_to": {
                    "type": "integer",
                    "default": 100,
                    "minimum": 1,
                    "description": "Target inventory level (S) when ordering"
                },
                "initial_inventory": {
                    "type": "integer",
                    "default": 50,
                    "minimum": 0,
                    "description": "Starting inventory level"
                },
                "demand_rate": {
                    "type": "number",
                    "default": 5.0,
                    "minimum": 0.001,
                    "description": "Average demand per time unit"
                },
                "lead_time": {
                    "type": "number",
                    "default": 5.0,
                    "minimum": 0,
                    "description": "Time between order and delivery"
                },
                "holding_cost": {
                    "type": "number",
                    "default": 1.0,
                    "minimum": 0,
                    "description": "Cost per unit per time unit held"
                },
                "stockout_cost": {
                    "type": "number",
                    "default": 10.0,
                    "minimum": 0,
                    "description": "Cost per unit of unmet demand"
                },
                "order_cost": {
                    "type": "number",
                    "default": 50.0,
                    "minimum": 0,
                    "description": "Fixed cost per order placed"
                },
                "sim_time": {
                    "type": "integer",
                    "default": 365,
                    "minimum": 1,
                    "description": "Simulation time (e.g., 365 days)"
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
                "total_demand": {
                    "type": "integer",
                    "description": "Total units demanded"
                },
                "total_fulfilled": {
                    "type": "integer",
                    "description": "Total units fulfilled"
                },
                "stockout_count": {
                    "type": "integer",
                    "description": "Number of stockout events"
                },
                "stockout_units": {
                    "type": "integer",
                    "description": "Total units of unmet demand"
                },
                "fill_rate": {
                    "type": "number",
                    "description": "Fraction of demand fulfilled"
                },
                "avg_inventory": {
                    "type": "number",
                    "description": "Average inventory level"
                },
                "num_orders": {
                    "type": "integer",
                    "description": "Number of orders placed"
                },
                "total_cost": {
                    "type": "number",
                    "description": "Total inventory cost (holding + stockout + order)"
                }
            }
        }

    def run(
        self,
        params: dict,
        callback: Optional[Callable] = None
    ) -> dict:
        validated = self.validate_params(params)

        reorder_point = validated["reorder_point"]
        order_up_to = validated["order_up_to"]
        initial_inventory = validated["initial_inventory"]
        demand_rate = validated["demand_rate"]
        lead_time = validated["lead_time"]
        holding_cost = validated["holding_cost"]
        stockout_cost = validated["stockout_cost"]
        order_cost = validated["order_cost"]
        sim_time = validated["sim_time"]
        random_seed = validated["random_seed"]

        # Metrics
        total_demand = 0
        total_fulfilled = 0
        stockout_count = 0
        stockout_units = 0
        inventory_samples = []
        num_orders = 0
        total_holding_cost = 0
        total_stockout_cost = 0
        total_order_cost = 0

        # State
        inventory = initial_inventory
        order_pending = False

        def demand_process(env):
            nonlocal inventory, total_demand, total_fulfilled, stockout_count, stockout_units
            nonlocal total_stockout_cost

            while True:
                # Demand arrives according to Poisson process
                yield env.timeout(random.expovariate(demand_rate))

                # Demand quantity (usually 1, but can be batched)
                demand_qty = random.randint(1, 3)
                total_demand += demand_qty

                self.emit_event(callback, EventType.ENTITY_ARRIVAL, env.now, {
                    "event": "demand",
                    "quantity": demand_qty,
                    "inventory_before": inventory
                })

                if inventory >= demand_qty:
                    inventory -= demand_qty
                    total_fulfilled += demand_qty
                else:
                    # Partial fulfillment
                    fulfilled = inventory
                    unfulfilled = demand_qty - inventory
                    total_fulfilled += fulfilled
                    stockout_units += unfulfilled
                    stockout_count += 1
                    total_stockout_cost += unfulfilled * stockout_cost
                    inventory = 0

                    self.emit_event(callback, EventType.STATE_CHANGE, env.now, {
                        "event": "stockout",
                        "unfulfilled": unfulfilled
                    })

        def reorder_process(env):
            nonlocal inventory, order_pending, num_orders, total_order_cost

            while True:
                yield env.timeout(1)  # Check every time unit

                # Check if we need to order
                if inventory <= reorder_point and not order_pending:
                    order_qty = order_up_to - inventory
                    order_pending = True
                    num_orders += 1
                    total_order_cost += order_cost

                    self.emit_event(callback, EventType.STATE_CHANGE, env.now, {
                        "event": "order_placed",
                        "quantity": order_qty,
                        "current_inventory": inventory
                    })

                    # Schedule delivery after lead time
                    env.process(delivery_process(env, order_qty))

        def delivery_process(env, quantity):
            nonlocal inventory, order_pending

            # Wait for lead time (with some variability)
            actual_lead_time = random.gauss(lead_time, lead_time * 0.1)
            actual_lead_time = max(0.5, actual_lead_time)
            yield env.timeout(actual_lead_time)

            inventory += quantity
            order_pending = False

            self.emit_event(callback, EventType.STATE_CHANGE, env.now, {
                "event": "delivery",
                "quantity": quantity,
                "new_inventory": inventory
            })

        def monitor_process(env):
            nonlocal total_holding_cost

            while True:
                inventory_samples.append(inventory)
                total_holding_cost += inventory * holding_cost
                yield env.timeout(1)

        # Set up environment
        random.seed(random_seed)
        env = simpy.Environment()

        self.emit_event(callback, EventType.START, 0, {
            "reorder_point": reorder_point,
            "order_up_to": order_up_to,
            "initial_inventory": initial_inventory
        })

        env.process(demand_process(env))
        env.process(reorder_process(env))
        env.process(monitor_process(env))
        env.run(until=sim_time)

        # Calculate metrics
        avg_inventory = round(np.mean(inventory_samples), 2) if inventory_samples else 0
        fill_rate = round(total_fulfilled / total_demand, 4) if total_demand > 0 else 1.0
        total_cost = round(total_holding_cost + total_stockout_cost + total_order_cost, 2)

        result = {
            "total_demand": total_demand,
            "total_fulfilled": total_fulfilled,
            "stockout_count": stockout_count,
            "stockout_units": stockout_units,
            "fill_rate": fill_rate,
            "avg_inventory": avg_inventory,
            "num_orders": num_orders,
            "total_cost": total_cost
        }

        self.emit_event(callback, EventType.END, sim_time, result)

        return result
