# ABOUTME: FastAPI server exposing simulation and workorder endpoints
# ABOUTME: Provides REST API for running simulations and managing workorders

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import random
import secrets
import uvicorn

from simulations import SimulationRegistry
from config import settings
from database.connection import init_db, get_db
from database.models import User, Tenant, SimulationRun
from auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from auth.dependencies import get_current_user, get_current_tenant, require_role
from auth.schemas import UserCreate, UserLogin, UserResponse, Token, TokenRefresh, TenantCreate, TenantResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize database on startup"""
    init_db()
    # Create default tenant if it doesn't exist
    from database.connection import SessionLocal
    db = SessionLocal()
    try:
        default_tenant = db.query(Tenant).filter(Tenant.name == settings.default_tenant_name).first()
        if not default_tenant:
            default_tenant = Tenant(
                name=settings.default_tenant_name,
                api_key=secrets.token_urlsafe(32)
            )
            db.add(default_tenant)
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="Simulation AI Agent",
    description="MCP-enabled simulation server with multiple simulation types",
    version="2.0.0",
    lifespan=lifespan
)

# Define input schema for backward compatibility
class SimulationInput(BaseModel):
    n_servers: int = 1
    arrival_rate: float = 5.0
    service_time: float = 3.0
    sim_time: int = 50
    random_seed: int = 42
    verbose: bool = False


# Generic simulation input
class GenericSimulationInput(BaseModel):
    params: dict = {}

# Define workorder line details schema
class ProductionLineDetail(BaseModel):
    line_name: str
    time_spent_days: float
    start_date: str
    end_date: str
    status: str

# Define workorder line configuration schema
class ProductionLineConfiguration(BaseModel):
    line_name: str
    configured_time_days: float
    line_type: str
    capacity_per_day: int
    priority: int

# Define workorder response schema
class WorkorderResponse(BaseModel):
    workorder_number: str
    total_processing_time_days: float
    production_lines: List[ProductionLineDetail]
    current_status: str
    created_date: str

# Define workorder configuration response schema
class WorkorderConfigurationResponse(BaseModel):
    workorder_number: str
    total_configured_time_days: float
    production_line_configs: List[ProductionLineConfiguration]
    workorder_type: str
    priority_level: str

@app.get("/")
def read_root():
    return {
        "message": "Simulation AI Agent API",
        "version": "2.0.0",
        "docs": "/docs"
    }


# ============================================================================
# Simulation Endpoints
# ============================================================================

@app.get("/simulations")
def list_simulations():
    """List all available simulation types with their schemas"""
    return {
        "simulations": SimulationRegistry.list_all()
    }


@app.get("/simulations/{sim_type}/schema")
def get_simulation_schema(sim_type: str):
    """Get parameter and metrics schema for a simulation type"""
    if not SimulationRegistry.is_registered(sim_type):
        raise HTTPException(
            status_code=404,
            detail=f"Simulation type '{sim_type}' not found. Available: {SimulationRegistry.list_names()}"
        )

    sim = SimulationRegistry.get(sim_type)
    return {
        "name": sim.name,
        "description": sim.description,
        "parameters": sim.get_parameter_schema(),
        "metrics": sim.get_metrics_schema()
    }


@app.post("/simulations/{sim_type}/run")
def run_simulation_generic(sim_type: str, input: GenericSimulationInput):
    """Run a simulation of the specified type"""
    if not SimulationRegistry.is_registered(sim_type):
        raise HTTPException(
            status_code=404,
            detail=f"Simulation type '{sim_type}' not found. Available: {SimulationRegistry.list_names()}"
        )

    sim = SimulationRegistry.get(sim_type)

    try:
        result = sim.run(input.params)
        return {
            "simulation_type": sim_type,
            "parameters": input.params,
            "results": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")


# Backward compatibility endpoint
@app.post("/simulate")
def simulate(input: SimulationInput):
    """
    Run queueing simulation (backward compatibility).
    Use /simulations/queueing/run for the new API.
    """
    sim = SimulationRegistry.get("queueing")
    result = sim.run({
        "n_servers": input.n_servers,
        "arrival_rate": input.arrival_rate,
        "service_time": input.service_time,
        "sim_time": input.sim_time,
        "random_seed": input.random_seed
    })
    return result

@app.get("/workorder/{workorder_number}")
def get_workorder_details(workorder_number: str):
    """
    Get detailed information about a specific workorder including production lines and time spent
    """
    # Define available production lines
    production_lines = ["1200REI", "1200GR35", "MH", "QC", "Assembly", "Packaging", "Shipping"]
    
    # Generate realistic workorder data (in a real scenario, this would come from a database)
    # For demonstration, we'll create random but realistic data
    random.seed(hash(workorder_number) % 1000)  # Use workorder number as seed for consistent results
    
    # Randomly select 3-5 production lines for this workorder
    num_lines = random.randint(3, 5)
    selected_lines = random.sample(production_lines, num_lines)
    
    # Generate line details with realistic timing
    line_details = []
    current_date = datetime.now() - timedelta(days=random.randint(10, 30))
    
    for i, line_name in enumerate(selected_lines):
        # Random processing time between 0.5 to 3 days
        time_spent = round(random.uniform(0.5, 3.0), 1)
        
        start_date = current_date
        end_date = start_date + timedelta(days=time_spent)
        
        # Determine status based on position in sequence
        if i == len(selected_lines) - 1:
            status = "Completed"
        elif i == len(selected_lines) - 2:
            status = "In Progress"
        else:
            status = "Completed"
        
        line_detail = ProductionLineDetail(
            line_name=line_name,
            time_spent_days=time_spent,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            status=status
        )
        line_details.append(line_detail)
        
        # Move to next line start date
        current_date = end_date + timedelta(days=random.randint(0, 2))  # Small gap between lines
    
    # Calculate total processing time
    total_time = sum(line.time_spent_days for line in line_details)
    
    # Determine current status
    current_status = "In Progress" if any(line.status == "In Progress" for line in line_details) else "Completed"
    
    response = WorkorderResponse(
        workorder_number=workorder_number,
        total_processing_time_days=round(total_time, 1),
        production_lines=line_details,
        current_status=current_status,
        created_date=(datetime.now() - timedelta(days=random.randint(30, 60))).strftime("%Y-%m-%d")
    )
    
    return response

@app.get("/workorder/{workorder_number}/configuration")
def get_workorder_configuration(workorder_number: str):
    """
    Get configured time and settings for each production line in a workorder
    """
    # Define available production lines (same as get_workorder_details)
    production_lines = ["1200REI", "1200GR35", "MH", "QC", "Assembly", "Packaging", "Shipping"]
    
    # Use the same seed as get_workorder_details to ensure same number of lines
    random.seed(hash(workorder_number) % 1000)
    
    # Select the same number of lines as get_workorder_details
    num_lines = random.randint(3, 5)
    selected_lines = random.sample(production_lines, num_lines)
    
    # Line type mappings
    line_types = {
        "1200REI": "Manufacturing",
        "1200GR35": "Manufacturing", 
        "MH": "Material Handling",
        "QC": "Quality Control",
        "Assembly": "Assembly",
        "Packaging": "Packaging",
        "Shipping": "Logistics"
    }
    
    # Generate line configurations with different timing than actual processing time
    line_configs = []
    total_configured_time = 0
    
    for i, line_name in enumerate(selected_lines):
        # Configured time is different from actual processing time
        # Usually configured time is the standard/planned time for the line
        configured_time = round(random.uniform(1.0, 4.0), 1)
        
        # Capacity per day (units that can be processed)
        capacity_per_day = random.randint(50, 200)
        
        # Priority level (1-5, where 1 is highest priority)
        priority = random.randint(1, 5)
        
        line_config = ProductionLineConfiguration(
            line_name=line_name,
            configured_time_days=configured_time,
            line_type=line_types.get(line_name, "General"),
            capacity_per_day=capacity_per_day,
            priority=priority
        )
        line_configs.append(line_config)
        total_configured_time += configured_time
    
    # Determine workorder type and priority level
    workorder_types = ["Standard", "Express", "Priority", "Custom"]
    workorder_type = random.choice(workorder_types)
    
    priority_levels = ["Low", "Medium", "High", "Critical"]
    priority_level = random.choice(priority_levels)
    
    response = WorkorderConfigurationResponse(
        workorder_number=workorder_number,
        total_configured_time_days=round(total_configured_time, 1),
        production_line_configs=line_configs,
        workorder_type=workorder_type,
        priority_level=priority_level
    )
    
    return response


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/auth/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Get default tenant
    tenant = db.query(Tenant).filter(Tenant.name == settings.default_tenant_name).first()
    if not tenant:
        raise HTTPException(status_code=500, detail="Default tenant not found")

    # Create user
    hashed_password = pwd_context.hash(user_data.password)
    user = User(
        tenant_id=tenant.id,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@app.post("/auth/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Login and get access/refresh tokens"""
    user = db.query(User).filter(User.email == login_data.email).first()

    if not user or not pwd_context.verify(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")

    access_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": user.tenant_id, "role": user.role}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "tenant_id": user.tenant_id}
    )

    return Token(access_token=access_token, refresh_token=refresh_token)


@app.post("/auth/refresh", response_model=Token)
def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    payload = verify_token(token_data.refresh_token, "refresh")

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    access_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": user.tenant_id, "role": user.role}
    )
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.id), "tenant_id": user.tenant_id}
    )

    return Token(access_token=access_token, refresh_token=new_refresh_token)


@app.get("/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


# ============================================================================
# Tenant Management (Admin only)
# ============================================================================

@app.post("/tenants", response_model=TenantResponse)
def create_tenant(
    tenant_data: TenantCreate,
    current_user: User = Depends(require_role(["admin", "superuser"])),
    db: Session = Depends(get_db)
):
    """Create a new tenant (admin only)"""
    existing = db.query(Tenant).filter(Tenant.name == tenant_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant name already exists")

    tenant = Tenant(
        name=tenant_data.name,
        api_key=secrets.token_urlsafe(32)
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return tenant


@app.get("/tenants/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: int,
    current_user: User = Depends(require_role(["admin", "superuser"])),
    db: Session = Depends(get_db)
):
    """Get tenant by ID (admin only)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0.0"}


@app.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)):
    """Readiness check - verifies database connection"""
    try:
        db.execute("SELECT 1")
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database not ready: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("server:app", host=settings.api_host, port=settings.api_port, reload=settings.debug)