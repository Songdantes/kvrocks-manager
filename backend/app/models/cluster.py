"""
Cluster and Node models
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.user import user_clusters
import enum


class ClusterType(str, enum.Enum):
    MASTER_SLAVE = "master_slave"
    SHARDING = "sharding"


class ClusterStatus(str, enum.Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DEPLOYING = "deploying"


class NodeRole(str, enum.Enum):
    MASTER = "master"
    SLAVE = "slave"


class NodeStatus(str, enum.Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    SYNCING = "syncing"


class Cluster(Base):
    __tablename__ = 'clusters'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    cluster_type = Column(Enum(ClusterType), nullable=False)
    status = Column(Enum(ClusterStatus), default=ClusterStatus.STOPPED)
    description = Column(String(500))
    owner_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # KVrocks Controller integration
    controller_id = Column(Integer, ForeignKey('kvrocks_controllers.id', ondelete='SET NULL'))
    namespace = Column(String(100), default='default')  # Controller namespace
    controller_cluster_name = Column(String(100))  # Name in controller (may differ from display name)
    controller_managed = Column(Boolean, default=False)  # Whether managed by controller
    controller_version = Column(Integer, default=0)  # Cluster version from controller

    # Relationships
    nodes = relationship('Node', back_populates='cluster', cascade='all, delete-orphan')
    users = relationship('User', secondary=user_clusters, back_populates='clusters')
    owner = relationship('User', foreign_keys=[owner_id])
    controller = relationship('KVrocksController', back_populates='clusters', foreign_keys=[controller_id])
    # Note: scaling_tasks relationship is defined in ScalingTask model via backref

    @property
    def node_count(self):
        return len(self.nodes)

    @property
    def master_count(self):
        return len([n for n in self.nodes if n.role == NodeRole.MASTER])

    @property
    def slave_count(self):
        return len([n for n in self.nodes if n.role == NodeRole.SLAVE])


class Node(Base):
    __tablename__ = 'nodes'

    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False)
    host = Column(String(100), nullable=False)
    port = Column(Integer, nullable=False)
    password = Column(String(255))  # Encrypted
    role = Column(Enum(NodeRole), nullable=False)
    status = Column(Enum(NodeStatus), default=NodeStatus.STOPPED)
    master_node_id = Column(Integer, ForeignKey('nodes.id'))  # For slave nodes
    cluster_node_id = Column(String(50))  # KVrocks Cluster Node ID
    slots_range = Column(String(500))  # Slot ranges, e.g., "0-5460,10923-16383"
    shard_index = Column(Integer)  # Shard index in kvrocks-controller
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cluster = relationship('Cluster', back_populates='nodes')
    master_node = relationship('Node', remote_side=[id], backref='slave_nodes')
    configs = relationship('NodeConfig', back_populates='node', cascade='all, delete-orphan')

    __table_args__ = (
        # Unique constraint on host:port combination
        {'sqlite_autoincrement': True},
    )

    @property
    def address(self):
        return f"{self.host}:{self.port}"


class NodeConfig(Base):
    __tablename__ = 'node_configs'

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False)
    config_key = Column(String(100), nullable=False)
    config_value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    node = relationship('Node', back_populates='configs')
