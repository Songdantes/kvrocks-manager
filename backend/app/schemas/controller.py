"""
KVrocks Controller schemas
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.kvrocks_controller import ControllerStatus


# ==================== Request Schemas ====================

class ControllerCreate(BaseModel):
    """Create a new controller"""
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    address: str = Field(..., description="Controller address (http://host:port)")
    description: Optional[str] = Field(None, max_length=500)

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        v = v.strip().rstrip('/')
        if not v.startswith(('http://', 'https://')):
            v = f'http://{v}'
        return v


class ControllerUpdate(BaseModel):
    """Update controller"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class ImportClustersRequest(BaseModel):
    """Request to import clusters from controller"""
    clusters: List[Dict[str, str]] = Field(
        ...,
        description="List of clusters to import: [{namespace: str, cluster: str}]"
    )


# ==================== Response Schemas ====================

class ControllerResponse(BaseModel):
    """Controller basic response"""
    id: int
    name: str
    address: str
    status: ControllerStatus
    version: Optional[str] = None
    description: Optional[str] = None
    cluster_count: int = 0
    last_check_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ControllerDetail(ControllerResponse):
    """Controller detail response"""
    last_error: Optional[str] = None
    clusters: List[Dict[str, Any]] = []


class DiscoveredNamespace(BaseModel):
    """Discovered namespace from controller"""
    namespace: str
    clusters: List[str]


class DiscoverResponse(BaseModel):
    """Response for discover endpoint"""
    controller_id: int
    address: str
    namespaces: List[DiscoveredNamespace]
    total_clusters: int


class ControllerCheckResponse(BaseModel):
    """Response for health check"""
    success: bool
    status: ControllerStatus
    version: Optional[str] = None
    error: Optional[str] = None


class ImportResult(BaseModel):
    """Single cluster import result"""
    namespace: str
    cluster: str
    success: bool
    cluster_id: Optional[int] = None
    error: Optional[str] = None


class ImportClustersResponse(BaseModel):
    """Response for import clusters"""
    controller_id: int
    results: List[ImportResult]
    imported_count: int
    failed_count: int
