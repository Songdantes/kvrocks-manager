"""
User, Role, Permission models
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.database import Base

# Association tables
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
)

role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
)

user_clusters = Table(
    'user_clusters',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('cluster_id', Integer, ForeignKey('clusters.id', ondelete='CASCADE'), primary_key=True)
)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100))
    phone = Column(String(20))
    status = Column(Boolean, default=True)  # True: enabled, False: disabled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    roles = relationship('Role', secondary=user_roles, back_populates='users')
    clusters = relationship('Cluster', secondary=user_clusters, back_populates='users')
    operation_logs = relationship('OperationLog', back_populates='user')

    @property
    def permissions(self):
        """Get all permissions from user's roles"""
        perms = set()
        for role in self.roles:
            for perm in role.permissions:
                perms.add(perm.code)
        return perms

    def has_permission(self, permission_code: str) -> bool:
        """Check if user has a specific permission"""
        # Super admin has all permissions
        for role in self.roles:
            if role.name == 'super_admin':
                return True
        return permission_code in self.permissions


class Role(Base):
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    is_builtin = Column(Boolean, default=False)  # Built-in roles cannot be deleted
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    users = relationship('User', secondary=user_roles, back_populates='roles')
    permissions = relationship('Permission', secondary=role_permissions, back_populates='roles')


class Permission(Base):
    __tablename__ = 'permissions'

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False)  # e.g., 'cluster:create'
    name = Column(String(100), nullable=False)
    module = Column(String(50))  # e.g., 'cluster', 'node', 'user'
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    roles = relationship('Role', secondary=role_permissions, back_populates='permissions')


class OperationLog(Base):
    __tablename__ = 'operation_logs'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    action = Column(String(100), nullable=False)  # e.g., 'cluster:create', 'node:restart'
    target_type = Column(String(50))  # e.g., 'cluster', 'node', 'user'
    target_id = Column(Integer)
    detail = Column(Text)  # JSON string with operation details
    ip_address = Column(String(50))
    status = Column(String(20), nullable=False)  # 'success', 'failed'
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship('User', back_populates='operation_logs')
