"""
User management API routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.database import get_db
from app.models import User, Role, Permission
from app.schemas import (
    UserCreate, UserUpdate, UserResponse, PasswordUpdate,
    RoleCreate, RoleUpdate, RoleResponse,
    PermissionCreate, PermissionResponse
)
from app.core.security import get_password_hash, verify_password, get_current_user
from app.core.permissions import PermissionChecker, Permissions

router = APIRouter(prefix="/users", tags=["Users"])
role_router = APIRouter(prefix="/roles", tags=["Roles"])
permission_router = APIRouter(prefix="/permissions", tags=["Permissions"])


# ==================== User Routes ====================

@router.get("", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.USER_READ]))
):
    """List all users"""
    query = select(User).options(selectinload(User.roles))

    if search:
        query = query.where(User.username.contains(search))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    return [
        UserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            phone=u.phone,
            status=u.status,
            created_at=u.created_at,
            updated_at=u.updated_at,
            roles=[{"id": r.id, "name": r.name, "description": r.description} for r in u.roles]
        )
        for u in users
    ]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.USER_CREATE]))
):
    """Create a new user"""
    # Check if username already exists
    existing = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Create user
    user = User(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        email=user_data.email,
        phone=user_data.phone
    )

    # Assign roles
    if user_data.role_ids:
        result = await db.execute(
            select(Role).where(Role.id.in_(user_data.role_ids))
        )
        roles = result.scalars().all()
        user.roles = roles

    db.add(user)
    await db.commit()

    # Reload user with roles
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user.id)
    )
    user = result.scalar_one()

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[{"id": r.id, "name": r.name, "description": r.description} for r in user.roles]
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.USER_READ]))
):
    """Get a user by ID"""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[{"id": r.id, "name": r.name, "description": r.description} for r in user.roles]
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.USER_UPDATE]))
):
    """Update a user"""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update fields
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.phone is not None:
        user.phone = user_data.phone
    if user_data.status is not None:
        user.status = user_data.status

    # Update roles
    if user_data.role_ids is not None:
        result = await db.execute(
            select(Role).where(Role.id.in_(user_data.role_ids))
        )
        roles = result.scalars().all()
        user.roles = roles

    await db.commit()

    # Reload user with roles
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    user = result.scalar_one()

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[{"id": r.id, "name": r.name, "description": r.description} for r in user.roles]
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.USER_DELETE]))
):
    """Delete a user"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    await db.delete(user)
    await db.commit()


@router.put("/{user_id}/password")
async def change_password(
    user_id: int,
    password_data: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    # Users can only change their own password
    if current_user.id != user_id:
        # Check if user has permission to change others' passwords
        if not current_user.has_permission(Permissions.USER_UPDATE):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify old password
    if not verify_password(password_data.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid old password"
        )

    # Update password
    user.password_hash = get_password_hash(password_data.new_password)
    await db.commit()

    return {"message": "Password changed successfully"}


# ==================== Role Routes ====================

@role_router.get("", response_model=List[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.ROLE_READ]))
):
    """List all roles"""
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions))
    )
    roles = result.scalars().all()
    return roles


@role_router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.ROLE_CREATE]))
):
    """Create a new role"""
    # Check if role name already exists
    existing = await db.execute(
        select(Role).where(Role.name == role_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role name already exists"
        )

    role = Role(
        name=role_data.name,
        description=role_data.description
    )

    # Assign permissions
    if role_data.permission_ids:
        result = await db.execute(
            select(Permission).where(Permission.id.in_(role_data.permission_ids))
        )
        permissions = result.scalars().all()
        role.permissions = permissions

    db.add(role)
    await db.commit()

    # Reload role with permissions
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role.id)
    )
    role = result.scalar_one()

    return role


@role_router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.ROLE_UPDATE]))
):
    """Update a role"""
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    if role_data.name is not None:
        role.name = role_data.name
    if role_data.description is not None:
        role.description = role_data.description
    if role_data.permission_ids is not None:
        result = await db.execute(
            select(Permission).where(Permission.id.in_(role_data.permission_ids))
        )
        permissions = result.scalars().all()
        role.permissions = permissions

    await db.commit()

    # Reload role with permissions
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )
    role = result.scalar_one()

    return role


@role_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.ROLE_DELETE]))
):
    """Delete a role"""
    result = await db.execute(
        select(Role).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    await db.delete(role)
    await db.commit()


# ==================== Permission Routes ====================

@permission_router.get("", response_model=List[PermissionResponse])
async def list_permissions(
    module: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.ROLE_READ]))
):
    """List all permissions"""
    query = select(Permission)
    if module:
        query = query.where(Permission.module == module)

    result = await db.execute(query)
    return result.scalars().all()
