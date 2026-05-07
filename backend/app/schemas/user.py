"""
User schemas
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# Base schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class RoleBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = None


class PermissionBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=100)
    module: Optional[str] = None


# Create schemas
class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)
    role_ids: Optional[List[int]] = []


class RoleCreate(RoleBase):
    permission_ids: Optional[List[int]] = []


class PermissionCreate(PermissionBase):
    pass


# Update schemas
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[bool] = None
    role_ids: Optional[List[int]] = None


class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=100)


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None


# Response schemas
class PermissionResponse(PermissionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class RoleResponse(RoleBase):
    id: int
    is_builtin: bool
    created_at: datetime
    permissions: List[PermissionResponse] = []

    class Config:
        from_attributes = True


class RoleSimple(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: int
    status: bool
    created_at: datetime
    updated_at: datetime
    roles: List[RoleSimple] = []

    class Config:
        from_attributes = True


class UserWithPermissions(UserResponse):
    permissions: List[str] = []


# Auth schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserWithPermissions


class TokenPayload(BaseModel):
    sub: int  # user_id
    exp: datetime
    username: str


# Operation log schemas
class OperationLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    detail: Optional[str]
    ip_address: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
