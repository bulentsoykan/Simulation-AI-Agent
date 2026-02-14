# ABOUTME: Pydantic schemas for authentication
# ABOUTME: Defines request/response models for auth endpoints

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response (no password)"""
    id: int
    tenant_id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Schema for token refresh request"""
    refresh_token: str


class TokenData(BaseModel):
    """Schema for decoded token data"""
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
    role: Optional[str] = None


class TenantCreate(BaseModel):
    """Schema for tenant creation"""
    name: str


class TenantResponse(BaseModel):
    """Schema for tenant response"""
    id: int
    name: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
