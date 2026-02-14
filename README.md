# Simulation AI Agent

[![GitHub](https://img.shields.io/badge/GitHub-Simulation--AI--Agent-blue?logo=github)](https://github.com/bulentsoykan/Simulation-AI-Agent)
[![Author](https://img.shields.io/badge/Author-Bulent%20Soykan-green)](https://github.com/bulentsoykan)

![Simulation AI Agent](Simulation%20AI%20Agent.png)

A plugin-based discrete event simulation server with MCP (Model Context Protocol) integration, enabling AI assistants to run and analyze simulations.

## Features

- **Plugin-based Simulation Engine**: Extensible architecture supporting multiple simulation types
- **Built-in Simulations**: Queueing, Manufacturing, Inventory, and Logistics
- **MCP Integration**: Expose simulations as tools for Claude and other AI assistants
- **JWT Authentication**: Secure API access with user/tenant management
- **Multi-tenant Support**: Row-level security for data isolation
- **Real-time WebSocket Updates**: Stream simulation events as they happen
- **Analytics & Reporting**: Aggregate statistics and trend analysis
- **ML Predictions**: PyTorch neural networks for outcome prediction
- **Prometheus Metrics**: Monitor API performance and simulation runs

## Quick Start

### Installation

```bash
# Clone and install
git clone https://github.com/bulentsoykan/Simulation-AI-Agent.git
cd Simulation-AI-Agent
pip install -r requirements.txt
```

### Running the Servers

```bash
# Terminal 1: Start FastAPI server (port 8000)
python server.py

# Terminal 2: Start MCP server (port 8001)
python mcp_server.py
```

The API will be available at http://localhost:8000 with interactive docs at http://localhost:8000/docs

## Simulation Types

### Queueing (M/M/c Queue)

Models customer arrivals, waiting, and service with multiple servers.

```bash
curl -X POST http://localhost:8000/simulations/queueing/run \
  -H "Content-Type: application/json" \
  -d '{"params": {"n_servers": 3, "arrival_rate": 10, "service_time": 2, "sim_time": 480}}'
```

**Parameters:**
- `n_servers`: Number of parallel service stations (default: 1)
- `arrival_rate`: Customer arrival rate per time unit (default: 5.0)
- `service_time`: Average service time per customer (default: 3.0)
- `sim_time`: Total simulation time (default: 1440)

**Metrics:**
- `total_customers`, `avg_wait_time`, `avg_system_time`, `max_wait_time`, `server_utilization`

### Manufacturing (Production Line)

Models work flowing through production stations with buffers.

```bash
curl -X POST http://localhost:8000/simulations/manufacturing/run \
  -H "Content-Type: application/json" \
  -d '{"params": {"stations": ["Cutting", "Assembly", "QC"], "processing_times": [2.0, 5.0, 1.5], "arrival_rate": 0.3}}'
```

**Parameters:**
- `stations`: Names of production stations in order
- `processing_times`: Processing time at each station
- `buffer_sizes`: Buffer capacity before each station
- `arrival_rate`: Raw material arrival rate

**Metrics:**
- `throughput`, `avg_cycle_time`, `wip`, `station_utilization`, `bottleneck_station`

### Inventory ((s,S) Policy)

Models inventory with reorder points and lead times.

```bash
curl -X POST http://localhost:8000/simulations/inventory/run \
  -H "Content-Type: application/json" \
  -d '{"params": {"reorder_point": 20, "order_up_to": 100, "demand_rate": 5.0, "lead_time": 5.0}}'
```

**Parameters:**
- `reorder_point`: Inventory level that triggers reorder (s)
- `order_up_to`: Target inventory level when ordering (S)
- `demand_rate`: Average demand per time unit
- `lead_time`: Time between order and delivery

**Metrics:**
- `total_demand`, `total_fulfilled`, `fill_rate`, `avg_inventory`, `stockout_count`, `total_cost`

### Logistics (Vehicle Routing)

Models capacitated vehicle routing for deliveries.

```bash
curl -X POST http://localhost:8000/simulations/logistics/run \
  -H "Content-Type: application/json" \
  -d '{"params": {"num_vehicles": 3, "vehicle_capacity": 100, "num_customers": 20}}'
```

**Parameters:**
- `num_vehicles`: Number of delivery vehicles
- `vehicle_capacity`: Capacity per vehicle
- `num_customers`: Number of customer locations
- `service_time`: Time to serve each customer

**Metrics:**
- `customers_served`, `customers_unserved`, `total_distance`, `vehicle_utilization`, `demand_fulfilled`

## API Endpoints

### Simulations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulations` | GET | List all available simulation types |
| `/simulations/{type}/schema` | GET | Get parameter schema for a simulation |
| `/simulations/{type}/run` | POST | Run a simulation |
| `/simulate` | POST | Run queueing simulation (legacy) |

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register new user |
| `/auth/login` | POST | Login and get tokens |
| `/auth/refresh` | POST | Refresh access token |
| `/auth/me` | GET | Get current user info |

### Analytics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analytics/simulation-summary` | GET | Get simulation run statistics |
| `/analytics/trends` | GET | Get metric trends over time |

### ML Predictions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict/{sim_type}` | GET | Predict simulation outcomes |
| `/ml/train` | POST | Train prediction model (admin) |
| `/ml/model-info` | GET | Get model information |

### Health & Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/health/ready` | GET | Readiness check (DB) |
| `/metrics` | GET | Prometheus metrics |

## MCP Tools

When connected via MCP, the following tools are available:

- **`list_simulations`**: List all available simulation types
- **`run_simulation(simulation_type, params)`**: Run any simulation type
- **`simulate(...)`**: Run queueing simulation (convenience wrapper)
- **`get_workorder_details(workorder_number)`**: Get workorder tracking info
- **`get_workorder_configuration(workorder_number)`**: Get workorder config

### Claude Desktop Integration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "simulation": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8001/mcp"]
    }
  }
}
```

## Adding Custom Simulations

Create a new simulation by extending `BaseSimulation`:

```python
from simulations.base import BaseSimulation
from simulations.registry import SimulationRegistry

@SimulationRegistry.register
class MySimulation(BaseSimulation):
    name = "my_simulation"
    description = "My custom simulation"

    def get_parameter_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "my_param": {"type": "number", "default": 1.0}
            }
        }

    def get_metrics_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "my_metric": {"type": "number"}
            }
        }

    def run(self, params: dict, callback=None) -> dict:
        validated = self.validate_params(params)
        # Run your simulation logic
        return {"my_metric": 42.0}
```

## Configuration

Environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./simulation.db` | Database connection string |
| `JWT_SECRET_KEY` | (generated) | Secret for JWT signing |
| `API_PORT` | `8000` | FastAPI server port |
| `MCP_PORT` | `8001` | MCP server port |
| `DEBUG` | `false` | Enable debug mode |

## Project Structure

```
simulation-ai-agent/
├── server.py              # FastAPI application
├── mcp_server.py          # MCP server
├── config.py              # Configuration settings
├── simulations/           # Simulation plugins
│   ├── base.py            # BaseSimulation class
│   ├── registry.py        # Plugin registry
│   ├── queueing.py        # M/M/c queue
│   ├── manufacturing.py   # Production line
│   ├── inventory.py       # Inventory management
│   └── logistics.py       # Vehicle routing
├── database/              # SQLAlchemy models
│   ├── connection.py      # DB session management
│   └── models.py          # ORM models
├── auth/                  # JWT authentication
│   ├── jwt_handler.py     # Token creation/validation
│   ├── dependencies.py    # FastAPI dependencies
│   └── schemas.py         # Pydantic schemas
├── analytics/             # Reporting
│   ├── aggregations.py    # Query aggregations
│   └── reports.py         # Report generation
├── ml/                    # Machine learning
│   ├── predictor.py       # PyTorch inference
│   └── trainer.py         # Model training
├── websocket/             # Real-time updates
│   └── manager.py         # Connection manager
└── monitoring/            # Prometheus metrics
    └── metrics.py         # Metric collectors
```

## Author

**Bulent Soykan**
- GitHub: [@bulentsoykan](https://github.com/bulentsoykan)
- Email: soykanb@gmail.com

## License

MIT


## Project Overview

A plugin-based MCP server exposing discrete event simulations to AI assistants. Features:
- Plugin-based simulation engine (queueing, manufacturing, inventory, logistics)
- JWT authentication with multi-tenant support
- Real-time WebSocket updates
- Analytics and ML-based prediction
- Prometheus monitoring

## Architecture

```
┌─────────────────┐    WS/HTTP   ┌─────────────────┐
│  MCP Clients    │ ◄──────────► │  mcp_server.py  │
└─────────────────┘    :8001     └────────┬────────┘
                                          │
┌─────────────────┐    WS/HTTP   ┌────────▼────────┐    ┌─────────────────┐
│  Web Clients    │ ◄──────────► │   server.py     │◄──►│  SQLite DB      │
└─────────────────┘    :8000     │   (FastAPI)     │    │  (SQLAlchemy)   │
                                 └────────┬────────┘    └─────────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │ simulations/    │         │  ml/            │         │  analytics/     │
    │  base.py        │         │  predictor.py   │         │  reports.py     │
    │  registry.py    │         │   (PyTorch)     │         │  aggregations.py│
    │  queueing.py    │         └─────────────────┘         └─────────────────┘
    │  manufacturing.py│
    │  inventory.py   │
    │  logistics.py   │
    └─────────────────┘
```

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Terminal 1: FastAPI server (port 8000)
python server.py

# Terminal 2: MCP server (port 8001)
python mcp_server.py
```

## Key Components

### Simulation Plugin System (`simulations/`)
- `base.py`: `BaseSimulation` abstract class with `run()`, `get_parameter_schema()`, `get_metrics_schema()`
- `registry.py`: `SimulationRegistry` for plugin discovery and instantiation
- Built-in types: `queueing`, `manufacturing`, `inventory`, `logistics`

### Authentication (`auth/`)
- JWT-based with access/refresh tokens
- Multi-tenant via `tenant_id` on all models
- Dependencies: `get_current_user`, `get_current_tenant`, `require_role()`

### Database (`database/`)
- SQLAlchemy ORM with SQLite (configurable to PostgreSQL)
- Models: `Tenant`, `User`, `SimulationRun`, `Workorder`

### ML Prediction (`ml/`)
- PyTorch neural networks trained on historical simulation data
- `SimulationPredictor` for inference, `SimulationTrainer` for training

## API Endpoints

| Category | Endpoint | Description |
|----------|----------|-------------|
| Simulations | `GET /simulations` | List simulation types |
| | `GET /simulations/{type}/schema` | Get parameter schema |
| | `POST /simulations/{type}/run` | Run simulation |
| Auth | `POST /auth/register` | Register user |
| | `POST /auth/login` | Get tokens |
| | `GET /auth/me` | Current user |
| Health | `GET /health` | Health check |
| | `GET /metrics` | Prometheus metrics |

## MCP Tools

- `list_simulations()`: List available simulation types
- `run_simulation(simulation_type, params)`: Run any simulation
- `simulate(...)`: Run queueing simulation (legacy)
- `get_workorder_details(workorder_number)`: Get workorder info
- `get_workorder_configuration(workorder_number)`: Get workorder config

## Adding a New Simulation

```python
from simulations.base import BaseSimulation
from simulations.registry import SimulationRegistry

@SimulationRegistry.register
class MySimulation(BaseSimulation):
    name = "my_simulation"
    description = "Description here"

    def get_parameter_schema(self) -> dict:
        return {"type": "object", "properties": {...}}

    def get_metrics_schema(self) -> dict:
        return {"type": "object", "properties": {...}}

    def run(self, params: dict, callback=None) -> dict:
        validated = self.validate_params(params)
        # Simulation logic here
        return {"metric": value}
```

## Configuration

Settings loaded from environment or `.env`:
- `DATABASE_URL`: Database connection (default: `sqlite:///./simulation.db`)
- `JWT_SECRET_KEY`: JWT signing secret
- `API_PORT` / `MCP_PORT`: Server ports (8000/8001)
- `DEBUG`: Enable debug mode
