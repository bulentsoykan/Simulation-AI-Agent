# ABOUTME: SQLAlchemy ORM models for the simulation application
# ABOUTME: Defines Tenant, User, SimulationRun, and Workorder tables

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class Tenant(Base):
    """Multi-tenant organization"""
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    api_key = Column(String(64), unique=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="tenant")
    simulation_runs = relationship("SimulationRun", back_populates="tenant")
    workorders = relationship("Workorder", back_populates="tenant")


class User(Base):
    """User account with tenant association"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="user")  # user, admin, superuser
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    simulation_runs = relationship("SimulationRun", back_populates="user")


class SimulationRun(Base):
    """Record of a simulation execution"""
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Simulation details
    simulation_type = Column(String(100), nullable=False, index=True)
    parameters = Column(JSON, nullable=False)
    results = Column(JSON)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    error_message = Column(Text)

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="simulation_runs")
    user = relationship("User", back_populates="simulation_runs")


class Workorder(Base):
    """Workorder tracking"""
    __tablename__ = "workorders"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    workorder_number = Column(String(100), nullable=False, index=True)
    status = Column(String(50), default="pending")
    workorder_type = Column(String(100))
    priority_level = Column(String(50))

    # Configuration
    configuration = Column(JSON)

    # Processing details
    production_lines = Column(JSON)
    total_processing_time_days = Column(Float)
    total_configured_time_days = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="workorders")
