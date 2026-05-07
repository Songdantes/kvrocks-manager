"""
Authentication API routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import User, Role, Permission, OperationLog
from app.schemas import LoginRequest, Token, UserWithPermissions
from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    get_current_user
)
from app.config import settings
from datetime import timedelta
import json

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """User login"""
    # Find user by username
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.username == login_data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password_hash):
        # Log failed login attempt
        log = OperationLog(
            action="auth:login",
            detail=json.dumps({"username": login_data.username}),
            ip_address=request.client.host if request.client else None,
            status="failed",
            error_message="Invalid username or password"
        )
        db.add(log)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if not user.status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # Create access token
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Get user permissions
    permissions = list(user.permissions)

    # Log successful login
    log = OperationLog(
        user_id=user.id,
        action="auth:login",
        ip_address=request.client.host if request.client else None,
        status="success"
    )
    db.add(log)
    await db.commit()

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserWithPermissions(
            id=user.id,
            username=user.username,
            email=user.email,
            phone=user.phone,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=[{"id": r.id, "name": r.name, "description": r.description} for r in user.roles],
            permissions=permissions
        )
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """User logout"""
    # Log logout
    log = OperationLog(
        user_id=current_user.id,
        action="auth:logout",
        ip_address=request.client.host if request.client else None,
        status="success"
    )
    db.add(log)
    await db.commit()

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserWithPermissions)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user information"""
    # Reload user with relationships
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == current_user.id)
    )
    user = result.scalar_one()

    permissions = list(user.permissions)

    return UserWithPermissions(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[{"id": r.id, "name": r.name, "description": r.description} for r in user.roles],
        permissions=permissions
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token"""
    # Reload user with relationships
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == current_user.id)
    )
    user = result.scalar_one()

    # Create new access token
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    permissions = list(user.permissions)

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserWithPermissions(
            id=user.id,
            username=user.username,
            email=user.email,
            phone=user.phone,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=[{"id": r.id, "name": r.name, "description": r.description} for r in user.roles],
            permissions=permissions
        )
    )
