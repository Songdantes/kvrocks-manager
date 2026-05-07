"""
Cluster scaling schemas

Adapted for Apache kvrocks-controller:
- Uses namespace/cluster/shard/node hierarchy
- Shard-based slot migration (not node-based)
- Controller handles migration coordination
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.scaling import TaskType, TaskStatus, SlotMigrationStatus


# ==================== Request Schemas ====================

class FailoverRequest(BaseModel):
    """Request for shard failover via kvrocks-controller"""
    shard_index: int = Field(..., description="Shard index to failover")
    preferred_node_id: Optional[str] = Field(None, description="Preferred node ID to promote (optional)")


class AddShardRequest(BaseModel):
    """Request to add a new shard to the cluster via kvrocks-controller"""
    nodes: List[str] = Field(..., min_length=1, description="Node addresses (host:port), first becomes master")
    password: Optional[str] = Field(None, description="Password for the nodes")


class RemoveShardRequest(BaseModel):
    """Request to remove a shard from the cluster"""
    shard_index: int = Field(..., description="Shard index to remove")
    target_shard_index: Optional[int] = Field(None, description="Target shard to migrate slots to")


class SlotMigrationRequest(BaseModel):
    """Request for slot migration via kvrocks-controller"""
    target_shard: int = Field(..., description="Target shard index")
    slot_start: int = Field(..., ge=0, le=16383, description="Start of slot range")
    slot_stop: int = Field(..., ge=0, le=16383, description="End of slot range (inclusive)")
    slot_only: bool = Field(False, description="Only migrate slot metadata without data")


class RebalanceRequest(BaseModel):
    """Request for cluster rebalancing"""
    threshold_percent: int = Field(2, ge=1, le=50, description="Rebalance threshold percentage")
    simulate: bool = Field(False, description="Simulate only, don't actually migrate")


class AddNodeRequest(BaseModel):
    """Request to add a node to a shard"""
    shard_index: int = Field(..., description="Shard index to add node to")
    addr: str = Field(..., description="Node address (host:port)")
    role: str = Field("slave", description="Node role: master or slave")
    password: Optional[str] = Field(None, description="Node password")


class RemoveNodeRequest(BaseModel):
    """Request to remove a node from a shard"""
    shard_index: int = Field(..., description="Shard index")
    node_id: str = Field(..., description="Node ID to remove")


class ImportClusterRequest(BaseModel):
    """Request to import an existing cluster into controller"""
    nodes: List[str] = Field(..., min_length=1, description="Node addresses to discover from")
    password: Optional[str] = Field(None, description="Cluster password")


class CreateClusterRequest(BaseModel):
    """Request to create a new cluster on controller"""
    nodes: List[str] = Field(..., min_length=3, description="Node addresses (host:port)")
    replicas: int = Field(0, ge=0, le=10, description="Number of replicas per shard")
    password: Optional[str] = Field(None, description="Cluster password")


class TaskControlRequest(BaseModel):
    """Request to control task execution"""
    action: str = Field(..., pattern="^(pause|resume)$", description="Control action: pause or resume")


class TaskCancelRequest(BaseModel):
    """Request to cancel a task"""
    rollback: bool = Field(False, description="Whether to rollback completed operations")


# ==================== Response Schemas ====================

class SlotRange(BaseModel):
    """Slot range representation"""
    start: int
    stop: int


class ControllerNodeInfo(BaseModel):
    """Node info from kvrocks-controller"""
    id: str
    addr: str
    role: str
    password: Optional[str] = None


class ControllerShardInfo(BaseModel):
    """Shard info from kvrocks-controller"""
    index: int
    nodes: List[ControllerNodeInfo]
    slot_ranges: List[SlotRange]
    migrating_slot: Optional[str] = None  # String format like "0-1" or "5461"
    target_shard_index: Optional[int] = None

    @property
    def slots_count(self) -> int:
        return sum(sr.stop - sr.start + 1 for sr in self.slot_ranges)

    @property
    def master_node(self) -> Optional[ControllerNodeInfo]:
        for node in self.nodes:
            if node.role == "master":
                return node
        return None


class ClusterTopology(BaseModel):
    """Cluster topology response from kvrocks-controller"""
    cluster_id: int
    cluster_name: str
    namespace: str
    version: int
    cluster_state: str = "ok"
    shards: List[ControllerShardInfo]
    total_slots: int = 0
    shard_count: int = 0
    node_count: int = 0
    updated_at: datetime


class ClusterNodeInfo(BaseModel):
    """Cluster node information (flattened view)"""
    node_id: str
    address: str
    host: str
    port: int
    role: str
    shard_index: int
    slots: List[SlotRange] = []
    slots_count: int = 0
    is_master: bool = False


class ScalingSuggestion(BaseModel):
    """Scaling suggestion"""
    type: str = Field(..., description="Suggestion type: scale_up, scale_down, rebalance, none")
    reason: str
    severity: str = Field("info", description="info, warning, critical")
    recommendation: str
    params: Optional[Dict[str, Any]] = None


class ScalingSuggestionsResponse(BaseModel):
    """Scaling suggestions response"""
    cluster_id: int
    suggestions: List[ScalingSuggestion]
    metrics: Dict[str, Any]


class ScalingSubtaskResponse(BaseModel):
    """Scaling subtask response"""
    id: int
    sequence: int
    slot_start: Optional[int]
    slot_end: Optional[int]
    source_node_id: Optional[str]
    target_node_id: Optional[str]
    status: SlotMigrationStatus
    keys_migrated: int = 0
    keys_total: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ScalingTaskLogResponse(BaseModel):
    """Scaling task log response"""
    id: int
    level: str
    message: str
    detail: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ScalingTaskResponse(BaseModel):
    """Scaling task response"""
    id: int
    cluster_id: int
    task_type: TaskType
    status: TaskStatus
    progress: int = 0
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    can_rollback: bool = True
    created_by: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class ScalingTaskDetail(ScalingTaskResponse):
    """Scaling task detail with subtasks and logs"""
    params: Dict[str, Any] = {}
    error_detail: Optional[str] = None
    rollback_data: Dict[str, Any] = {}
    subtasks: List[ScalingSubtaskResponse] = []
    logs: List[ScalingTaskLogResponse] = []


class ScalingTaskListResponse(BaseModel):
    """Paginated scaling task list"""
    tasks: List[ScalingTaskResponse]
    total: int
    page: int
    page_size: int


class TaskOperationResponse(BaseModel):
    """Task operation response"""
    success: bool
    task_id: Optional[int] = None
    message: str
    error: Optional[str] = None


class ControllerOperationResponse(BaseModel):
    """Direct controller operation response (no task created)"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ==================== Migration Plan Schemas ====================

class SlotMigrationPlan(BaseModel):
    """Single slot migration plan"""
    slot_start: int
    slot_end: int
    source_shard: int
    target_shard: int
    estimated_keys: int = 0


class MigrationPlanResponse(BaseModel):
    """Migration plan response"""
    cluster_id: int
    task_type: TaskType
    plan: List[SlotMigrationPlan]
    total_slots: int
    estimated_keys: int

