"""
Cluster scaling task models
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship, backref
from app.database import Base
import enum


class TaskType(str, enum.Enum):
    """Scaling task types"""
    FAILOVER = "failover"
    ADD_SHARD = "add_shard"
    REMOVE_SHARD = "remove_shard"
    SLOT_MIGRATION = "slot_migration"
    REBALANCE = "rebalance"


class TaskStatus(str, enum.Enum):
    """Scaling task status"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLING_BACK = "rolling_back"


class SlotMigrationStatus(str, enum.Enum):
    """Slot migration subtask status"""
    PENDING = "pending"
    IMPORTING = "importing"
    MIGRATING = "migrating"
    MOVING_KEYS = "moving_keys"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


class ScalingTask(Base):
    """Main scaling task table"""
    __tablename__ = 'scaling_tasks'

    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)

    # Task parameters (JSON)
    params = Column(JSON, nullable=False, default={})

    # Progress information
    progress = Column(Integer, default=0)  # 0-100
    current_step = Column(String(200))

    # Error information
    error_message = Column(Text)
    error_detail = Column(Text)

    # Rollback data
    rollback_data = Column(JSON, default={})
    can_rollback = Column(Boolean, default=True)

    # Audit information
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cluster = relationship('Cluster', backref=backref('scaling_tasks', cascade='all, delete-orphan', passive_deletes=True))
    creator = relationship('User', foreign_keys=[created_by])
    subtasks = relationship('ScalingSubtask', back_populates='task',
                            cascade='all, delete-orphan', order_by='ScalingSubtask.sequence')
    logs = relationship('ScalingTaskLog', back_populates='task',
                        cascade='all, delete-orphan', order_by='ScalingTaskLog.created_at')


class ScalingSubtask(Base):
    """Scaling subtask table - for multi-step operations like slot migration"""
    __tablename__ = 'scaling_subtasks'

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey('scaling_tasks.id', ondelete='CASCADE'), nullable=False)
    sequence = Column(Integer, nullable=False)

    # Slot migration specific fields
    slot_start = Column(Integer)
    slot_end = Column(Integer)
    source_node_id = Column(String(50))
    target_node_id = Column(String(50))

    status = Column(Enum(SlotMigrationStatus), default=SlotMigrationStatus.PENDING)
    keys_migrated = Column(Integer, default=0)
    keys_total = Column(Integer, default=0)

    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    task = relationship('ScalingTask', back_populates='subtasks')


class ScalingTaskLog(Base):
    """Scaling task log table"""
    __tablename__ = 'scaling_task_logs'

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey('scaling_tasks.id', ondelete='CASCADE'), nullable=False)
    level = Column(String(20), default='info')  # info, warning, error
    message = Column(Text, nullable=False)
    detail = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    task = relationship('ScalingTask', back_populates='logs')


class ClusterSlotInfo(Base):
    """Cluster slot information cache table"""
    __tablename__ = 'cluster_slot_info'

    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False)
    node_id = Column(String(50), nullable=False)  # Cluster Node ID
    node_address = Column(String(100))
    role = Column(String(20))  # master/slave
    master_id = Column(String(50))
    slots = Column(JSON)  # Slot ranges list
    keys_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cluster = relationship('Cluster', backref=backref('slot_info', cascade='all, delete-orphan', passive_deletes=True))
