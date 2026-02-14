# ABOUTME: Prometheus metrics collection for the simulation API
# ABOUTME: Tracks request counts, latencies, and simulation run statistics

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from typing import Optional
import time


class SimulationMetrics:
    """
    Prometheus metrics for simulation monitoring.
    """

    # Request metrics
    request_count = Counter(
        "simulation_api_requests_total",
        "Total API requests",
        ["method", "endpoint", "status_code"]
    )

    request_latency = Histogram(
        "simulation_api_request_latency_seconds",
        "Request latency in seconds",
        ["method", "endpoint"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )

    # Simulation metrics
    simulation_runs_total = Counter(
        "simulation_runs_total",
        "Total simulation runs",
        ["simulation_type", "status"]
    )

    simulation_duration = Histogram(
        "simulation_duration_seconds",
        "Simulation execution duration",
        ["simulation_type"],
        buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
    )

    # Current state metrics
    active_simulations = Gauge(
        "simulation_active_count",
        "Number of currently running simulations",
        ["simulation_type"]
    )

    websocket_connections = Gauge(
        "websocket_connections_total",
        "Number of active WebSocket connections"
    )

    # Database metrics
    db_query_duration = Histogram(
        "db_query_duration_seconds",
        "Database query duration",
        ["operation"],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
    )

    # ML metrics
    ml_prediction_duration = Histogram(
        "ml_prediction_duration_seconds",
        "ML prediction duration",
        ["simulation_type"]
    )

    ml_training_duration = Histogram(
        "ml_training_duration_seconds",
        "ML model training duration",
        ["simulation_type"]
    )


# Convenience functions for recording metrics

def record_simulation_run(
    simulation_type: str,
    status: str,
    duration_seconds: Optional[float] = None
):
    """Record a simulation run completion"""
    SimulationMetrics.simulation_runs_total.labels(
        simulation_type=simulation_type,
        status=status
    ).inc()

    if duration_seconds is not None:
        SimulationMetrics.simulation_duration.labels(
            simulation_type=simulation_type
        ).observe(duration_seconds)


def record_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration_seconds: float
):
    """Record an API request"""
    SimulationMetrics.request_count.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code)
    ).inc()

    SimulationMetrics.request_latency.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration_seconds)


def get_metrics_text() -> bytes:
    """Generate Prometheus metrics text format"""
    return generate_latest()


def get_content_type() -> str:
    """Get content type for Prometheus metrics"""
    return CONTENT_TYPE_LATEST


class MetricsMiddleware:
    """
    ASGI middleware for automatic request metrics collection.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        status_code = 500  # Default if exception occurs

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            path = scope.get("path", "unknown")
            method = scope.get("method", "unknown")

            # Normalize paths with IDs
            normalized_path = path
            for segment in path.split("/"):
                if segment.isdigit():
                    normalized_path = normalized_path.replace(f"/{segment}", "/{id}")

            record_request(method, normalized_path, status_code, duration)
