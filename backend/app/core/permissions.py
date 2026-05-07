"""
Permission control utilities
"""
from functools import wraps
from typing import List, Callable
from fastapi import HTTPException, status, Depends
from app.models.user import User
from app.core.security import get_current_user


class PermissionChecker:
    """
    Permission checker dependency
    Usage:
        @router.get("/clusters", dependencies=[Depends(PermissionChecker(["cluster:read"]))])
        async def list_clusters():
            pass
    """

    def __init__(self, required_permissions: List[str]):
        self.required_permissions = required_permissions

    async def __call__(self, current_user: User = Depends(get_current_user)) -> bool:
        # Super admin has all permissions
        for role in current_user.roles:
            if role.name == 'super_admin':
                return True

        # Check if user has all required permissions
        user_permissions = current_user.permissions
        for permission in self.required_permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission} required"
                )
        return True


def require_permissions(permissions: List[str]):
    """
    Decorator for requiring permissions
    Usage:
        @require_permissions(["cluster:read"])
        async def list_clusters(current_user: User = Depends(get_current_user)):
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, current_user: User, **kwargs):
            # Super admin has all permissions
            for role in current_user.roles:
                if role.name == 'super_admin':
                    return await func(*args, current_user=current_user, **kwargs)

            # Check permissions
            user_permissions = current_user.permissions
            for permission in permissions:
                if permission not in user_permissions:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: {permission} required"
                    )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


# Common permission codes
class Permissions:
    # User management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # Role management
    ROLE_CREATE = "role:create"
    ROLE_READ = "role:read"
    ROLE_UPDATE = "role:update"
    ROLE_DELETE = "role:delete"

    # Cluster management
    CLUSTER_CREATE = "cluster:create"
    CLUSTER_READ = "cluster:read"
    CLUSTER_UPDATE = "cluster:update"
    CLUSTER_DELETE = "cluster:delete"

    # Node management
    NODE_CREATE = "node:create"
    NODE_READ = "node:read"
    NODE_UPDATE = "node:update"
    NODE_DELETE = "node:delete"
    NODE_OPERATE = "node:operate"  # start, stop, restart

    # Config management
    CONFIG_READ = "config:read"
    CONFIG_UPDATE = "config:update"

    # Command execution
    COMMAND_EXECUTE = "command:execute"

    # Backup management
    BACKUP_CREATE = "backup:create"
    BACKUP_READ = "backup:read"
    BACKUP_RESTORE = "backup:restore"
    BACKUP_DELETE = "backup:delete"

    # Scaling operations
    SCALING_READ = "scaling:read"       # View scaling tasks and topology
    SCALING_EXECUTE = "scaling:execute" # Execute scaling operations
    SCALING_CANCEL = "scaling:cancel"   # Cancel scaling tasks
    SCALING_ROLLBACK = "scaling:rollback"  # Rollback scaling tasks


# Default role permissions
DEFAULT_ROLE_PERMISSIONS = {
    "super_admin": [],  # Has all permissions implicitly
    "cluster_admin": [
        Permissions.CLUSTER_CREATE, Permissions.CLUSTER_READ, Permissions.CLUSTER_UPDATE, Permissions.CLUSTER_DELETE,
        Permissions.NODE_CREATE, Permissions.NODE_READ, Permissions.NODE_UPDATE, Permissions.NODE_DELETE,
        Permissions.NODE_OPERATE,
        Permissions.CONFIG_READ, Permissions.CONFIG_UPDATE,
        Permissions.COMMAND_EXECUTE,
        Permissions.BACKUP_CREATE, Permissions.BACKUP_READ, Permissions.BACKUP_RESTORE, Permissions.BACKUP_DELETE,
        Permissions.SCALING_READ, Permissions.SCALING_EXECUTE, Permissions.SCALING_CANCEL, Permissions.SCALING_ROLLBACK,
    ],
    "operator": [
        Permissions.CLUSTER_READ,
        Permissions.NODE_READ, Permissions.NODE_OPERATE,
        Permissions.CONFIG_READ,
        Permissions.COMMAND_EXECUTE,
        Permissions.BACKUP_READ,
        Permissions.SCALING_READ,
    ],
    "readonly": [
        Permissions.CLUSTER_READ,
        Permissions.NODE_READ,
        Permissions.CONFIG_READ,
        Permissions.BACKUP_READ,
        Permissions.SCALING_READ,
    ],
}
