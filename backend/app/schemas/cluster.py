"""
Cluster and Node schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.cluster import ClusterType, ClusterStatus, NodeRole, NodeStatus


# Cluster schemas
class ClusterBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    cluster_type: ClusterType
    description: Optional[str] = None


class ClusterCreate(ClusterBase):
    controller_id: Optional[int] = None


class ClusterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None


class NodeBase(BaseModel):
    host: str = Field(..., min_length=1, max_length=100)
    port: int = Field(..., ge=1, le=65535)
    password: Optional[str] = None
    role: NodeRole


class NodeCreate(NodeBase):
    cluster_id: int
    master_node_id: Optional[int] = None


class NodeUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[NodeRole] = None
    master_node_id: Optional[int] = None


class NodeConfigUpdate(BaseModel):
    configs: Dict[str, str]


# Response schemas
class NodeConfigResponse(BaseModel):
    config_key: str
    config_value: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


class NodeResponse(NodeBase):
    id: int
    cluster_id: int
    status: NodeStatus
    master_node_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NodeDetail(NodeResponse):
    configs: List[NodeConfigResponse] = []
    cluster_name: Optional[str] = None


class ClusterResponse(ClusterBase):
    id: int
    status: ClusterStatus
    owner_id: Optional[int]
    controller_id: Optional[int] = None
    controller_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    node_count: int = 0
    master_count: int = 0
    slave_count: int = 0

    class Config:
        from_attributes = True


class ClusterDetail(ClusterResponse):
    nodes: List[NodeResponse] = []


# Command execution
class CommandRequest(BaseModel):
    command: str = Field(..., min_length=1)
    args: Optional[List[str]] = []


class CommandResponse(BaseModel):
    success: bool
    result: Any
    error: Optional[str] = None


# Node info response
class NodeInfoResponse(BaseModel):
    success: bool
    info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# Batch operations
class BatchNodeIds(BaseModel):
    node_ids: List[int]


class BatchOperationResult(BaseModel):
    success: List[int]
    failed: List[Dict[str, Any]]
