"""
Cluster scaling API routes

Adapted for Apache kvrocks-controller:
- Operations are delegated to kvrocks-controller via HTTP API
- Controller handles cluster coordination, slot migration, failover
- Uses namespace/cluster/shard/node hierarchy
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.config import settings
from app.models import Cluster, Node, User, NodeRole, NodeStatus
from app.models.scaling import (
    ScalingTask, ScalingSubtask, ScalingTaskLog,
    TaskType, TaskStatus, SlotMigrationStatus
)
from app.schemas.scaling import (
    FailoverRequest, AddShardRequest, RemoveShardRequest,
    SlotMigrationRequest, RebalanceRequest,
    AddNodeRequest, RemoveNodeRequest, ImportClusterRequest, CreateClusterRequest,
    TaskControlRequest, TaskCancelRequest,
    ClusterTopology, ControllerShardInfo, ControllerNodeInfo, SlotRange,
    ClusterNodeInfo, ScalingSuggestion, ScalingSuggestionsResponse,
    ScalingTaskResponse, ScalingTaskDetail, ScalingTaskListResponse,
    ScalingSubtaskResponse, ScalingTaskLogResponse,
    TaskOperationResponse, ControllerOperationResponse,
    MigrationPlanResponse, SlotMigrationPlan
)
from app.services.controller import (
    AsyncKVrocksControllerClient, ControllerAPIError
)
from app.services.kvrocks import create_kvrocks_client
from app.core.security import get_current_user
from app.core.permissions import PermissionChecker, Permissions
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clusters/{cluster_id}/scaling", tags=["Scaling"])


# ==================== Helper Functions ====================

async def get_cluster_or_404(cluster_id: int, db: AsyncSession) -> Cluster:
    """Get cluster or raise 404"""
    result = await db.execute(
        select(Cluster)
        .options(selectinload(Cluster.nodes), selectinload(Cluster.controller))
        .where(Cluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )
    return cluster


async def get_task_or_404(task_id: int, cluster_id: int, db: AsyncSession) -> ScalingTask:
    """Get task or raise 404"""
    result = await db.execute(
        select(ScalingTask)
        .options(
            selectinload(ScalingTask.subtasks),
            selectinload(ScalingTask.logs)
        )
        .where(
            ScalingTask.id == task_id,
            ScalingTask.cluster_id == cluster_id
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return task


def get_controller_client(cluster: Cluster = None) -> AsyncKVrocksControllerClient:
    """Get controller client from cluster or global settings"""
    if cluster and cluster.controller:
        return AsyncKVrocksControllerClient(
            controller_url=cluster.controller.address,
            timeout=settings.KVROCKS_CONTROLLER_TIMEOUT,
            username=None,  # Can be extended if controller has auth
            password=None
        )
    if settings.KVROCKS_CONTROLLER_URL:
        return AsyncKVrocksControllerClient(
            controller_url=settings.KVROCKS_CONTROLLER_URL,
            timeout=settings.KVROCKS_CONTROLLER_TIMEOUT,
            username=settings.KVROCKS_CONTROLLER_USERNAME,
            password=settings.KVROCKS_CONTROLLER_PASSWORD
        )
    raise HTTPException(
        status_code=400,
        detail="No controller configured for this cluster. Please bind a controller first."
    )


# ==================== Topology Routes ====================

@router.get("/topology", response_model=ClusterTopology)
async def get_cluster_topology(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_READ]))
):
    """
    Get cluster topology from kvrocks-controller

    Returns the cluster structure including shards, nodes, and slot distribution.
    """
    cluster = await get_cluster_or_404(cluster_id, db)

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            cluster_data = await client.get_cluster(namespace, controller_cluster)
            logger.info(f"Controller returned cluster_data: {cluster_data}")

            # Parse shards
            shards = []
            total_slots = 0
            node_count = 0

            for idx, shard_data in enumerate(cluster_data.get("shards", [])):
                # Parse nodes
                nodes = []
                for node_data in shard_data.get("nodes", []):
                    nodes.append(ControllerNodeInfo(
                        id=node_data.get("id", ""),
                        addr=node_data.get("addr", ""),
                        role=node_data.get("role", "slave"),
                        password=None  # Don't expose password
                    ))
                    node_count += 1

                # Parse slot ranges - handle both formats:
                # 1. String array: ["0-5460", "10923-16383"]
                # 2. Object array: [{"start": 0, "stop": 5460}]
                slot_ranges = []
                raw_ranges = shard_data.get("slot_ranges") or shard_data.get("slotRanges") or []
                for sr in raw_ranges:
                    if isinstance(sr, str):
                        # Parse string format "0-5460" or "5461"
                        if "-" in sr:
                            start, stop = sr.split("-", 1)
                            start, stop = int(start), int(stop)
                        else:
                            start = stop = int(sr)
                    else:
                        # Object format {"start": 0, "stop": 5460}
                        start = sr.get("start", 0)
                        stop = sr.get("stop", 0)

                    slot_ranges.append(SlotRange(start=start, stop=stop))
                    total_slots += stop - start + 1

                migrating_slot_raw = shard_data.get("migrating_slot")
                if migrating_slot_raw is not None and migrating_slot_raw != -1 and migrating_slot_raw != "":
                    migrating_slot_val = str(migrating_slot_raw)
                else:
                    migrating_slot_val = None

                shards.append(ControllerShardInfo(
                    index=idx,
                    nodes=nodes,
                    slot_ranges=slot_ranges,
                    migrating_slot=migrating_slot_val,
                    target_shard_index=shard_data.get("target_shard_index")
                ))

            return ClusterTopology(
                cluster_id=cluster_id,
                cluster_name=cluster.name,
                namespace=namespace,
                version=cluster_data.get("version", 0),
                cluster_state="ok",
                shards=shards,
                total_slots=total_slots,
                shard_count=len(shards),
                node_count=node_count,
                updated_at=datetime.utcnow()
            )

    except ControllerAPIError as e:
        logger.error(f"Controller API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Controller error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Failed to get topology: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get topology: {str(e)}"
        )


@router.post("/topology/sync", response_model=ControllerOperationResponse)
async def sync_topology_to_db(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_READ]))
):
    """
    Sync cluster topology from controller to local database

    Updates local node records to match controller state.
    """
    cluster = await get_cluster_or_404(cluster_id, db)

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            cluster_data = await client.get_cluster(namespace, controller_cluster)

            # Update cluster version
            cluster.controller_version = cluster_data.get("version", 0)
            cluster.controller_managed = True

            # Track existing nodes
            existing_nodes = {f"{n.host}:{n.port}": n for n in cluster.nodes}
            seen_addresses = set()

            # Sync nodes from each shard
            for shard_idx, shard_data in enumerate(cluster_data.get("shards", [])):
                # Calculate slot range string - handle both formats
                raw_ranges = shard_data.get("slot_ranges") or shard_data.get("slotRanges") or []
                slots_parts = []
                for sr in raw_ranges:
                    if isinstance(sr, str):
                        slots_parts.append(sr)
                    else:
                        if sr['start'] != sr['stop']:
                            slots_parts.append(f"{sr['start']}-{sr['stop']}")
                        else:
                            slots_parts.append(str(sr['start']))
                slots_str = ",".join(slots_parts)

                for node_data in shard_data.get("nodes", []):
                    addr = node_data.get("addr", "")
                    if not addr:
                        continue

                    seen_addresses.add(addr)
                    host, port = addr.rsplit(":", 1)
                    port = int(port)
                    role = NodeRole.MASTER if node_data.get("role") == "master" else NodeRole.SLAVE

                    if addr in existing_nodes:
                        # Update existing node
                        node = existing_nodes[addr]
                        node.cluster_node_id = node_data.get("id")
                        node.role = role
                        node.shard_index = shard_idx
                        if role == NodeRole.MASTER:
                            node.slots_range = slots_str
                    else:
                        # Create new node
                        node = Node(
                            cluster_id=cluster_id,
                            host=host,
                            port=port,
                            role=role,
                            status=NodeStatus.RUNNING,
                            cluster_node_id=node_data.get("id"),
                            shard_index=shard_idx,
                            slots_range=slots_str if role == NodeRole.MASTER else None
                        )
                        db.add(node)

            # Remove nodes not in controller
            for addr, node in existing_nodes.items():
                if addr not in seen_addresses:
                    await db.delete(node)

            await db.commit()

            return ControllerOperationResponse(
                success=True,
                message="Topology synced successfully",
                data={"version": cluster.controller_version, "node_count": len(seen_addresses)}
            )

    except ControllerAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Controller error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Failed to sync topology: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync topology: {str(e)}"
        )


@router.post("/import", response_model=ControllerOperationResponse)
async def import_cluster_to_controller(
    cluster_id: int,
    request: ImportClusterRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_EXECUTE]))
):
    """
    Import an existing cluster into kvrocks-controller

    The controller will discover the cluster topology from the provided nodes.
    If cluster already exists in controller, it will sync the topology instead.
    """
    cluster = await get_cluster_or_404(cluster_id, db)

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            # Ensure namespace exists
            if not await client.namespace_exists(namespace):
                await client.create_namespace(namespace)

            # Try to import cluster
            try:
                result = await client.import_cluster(
                    namespace=namespace,
                    cluster_name=controller_cluster,
                    nodes=request.nodes,
                    password=request.password
                )
                message = "Cluster imported successfully"
            except ControllerAPIError as e:
                # If cluster already exists (409 Conflict), get existing cluster info
                if e.status_code == 409:
                    logger.info(f"Cluster already exists in controller, fetching existing topology")
                    result = await client.get_cluster(namespace, controller_cluster)
                    message = "Cluster already exists in controller, topology synced"
                else:
                    raise

            # Update cluster record
            cluster.controller_managed = True
            cluster.controller_cluster_name = controller_cluster
            cluster.namespace = namespace
            cluster.controller_version = result.get("version", 0)
            await db.commit()

            return ControllerOperationResponse(
                success=True,
                message=message,
                data={"version": result.get("version", 0), "shards": len(result.get("shards", []))}
            )

    except ControllerAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Controller error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Failed to import cluster: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import cluster: {str(e)}"
        )


@router.post("/create", response_model=ControllerOperationResponse)
async def create_cluster_on_controller(
    cluster_id: int,
    request: CreateClusterRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_EXECUTE]))
):
    """
    Create a new cluster on kvrocks-controller

    This creates a new sharding cluster with the specified nodes.
    The controller will automatically distribute slots and set up replication.
    """
    cluster = await get_cluster_or_404(cluster_id, db)

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            # Ensure namespace exists
            if not await client.namespace_exists(namespace):
                await client.create_namespace(namespace)

            # Create cluster on controller
            result = await client.create_cluster(
                namespace=namespace,
                cluster_name=controller_cluster,
                nodes=request.nodes,
                replicas=request.replicas,
                password=request.password
            )

            # Update cluster record
            cluster.controller_managed = True
            cluster.controller_cluster_name = controller_cluster
            cluster.namespace = namespace
            cluster.controller_version = result.get("version", 0)
            await db.commit()

            return ControllerOperationResponse(
                success=True,
                message="Cluster created successfully",
                data={"version": result.get("version", 0), "shards": len(result.get("shards", []))}
            )

    except ControllerAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Controller error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Failed to create cluster: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create cluster: {str(e)}"
        )


# ==================== Suggestions Routes ====================

@router.get("/suggestions", response_model=ScalingSuggestionsResponse)
async def get_scaling_suggestions(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_READ]))
):
    """Get scaling suggestions based on cluster metrics"""
    cluster = await get_cluster_or_404(cluster_id, db)

    suggestions = []
    metrics = {
        "total_memory": 0,
        "used_memory": 0,
        "total_keys": 0,
        "shard_count": 0,
        "slots_distribution": []
    }

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            cluster_data = await client.get_cluster(namespace, controller_cluster)
            shards = cluster_data.get("shards", [])
            metrics["shard_count"] = len(shards)

            # Analyze slot distribution
            shard_slots = []
            for idx, shard in enumerate(shards):
                slots_count = sum(
                    sr.get("stop", 0) - sr.get("start", 0) + 1
                    for sr in shard.get("slotRanges", [])
                )
                shard_slots.append({"shard": idx, "slots": slots_count})
                metrics["slots_distribution"].append({"shard": idx, "slots": slots_count})

            # Check slot balance
            if shard_slots:
                avg_slots = sum(s["slots"] for s in shard_slots) / len(shard_slots)
                max_deviation = max(
                    abs(s["slots"] - avg_slots) / avg_slots * 100
                    for s in shard_slots
                ) if avg_slots > 0 else 0

                if max_deviation > 20:
                    suggestions.append(ScalingSuggestion(
                        type="rebalance",
                        reason=f"Slot distribution is uneven (max deviation: {max_deviation:.1f}%)",
                        severity="info",
                        recommendation="Consider rebalancing slots across shards",
                        params={"max_deviation_percent": max_deviation}
                    ))

            # Check if any shard has no replicas
            for idx, shard in enumerate(shards):
                nodes = shard.get("nodes", [])
                masters = [n for n in nodes if n.get("role") == "master"]
                slaves = [n for n in nodes if n.get("role") == "slave"]
                if masters and not slaves:
                    suggestions.append(ScalingSuggestion(
                        type="add_replica",
                        reason=f"Shard {idx} has no replicas",
                        severity="warning",
                        recommendation=f"Add a replica node to shard {idx} for high availability",
                        params={"shard_index": idx}
                    ))

        # Get memory metrics from nodes
        for node in cluster.nodes:
            try:
                kv_client = create_kvrocks_client(node.host, node.port, node.password)
                info = kv_client.info()
                metrics["used_memory"] += float(info.get("used_memory", 0))
                metrics["total_memory"] += float(info.get("maxmemory", 0))
                kv_client.close()
            except Exception:
                continue

        # Memory-based suggestions
        if metrics["total_memory"] > 0:
            usage_percent = (metrics["used_memory"] / metrics["total_memory"]) * 100
            if usage_percent > 80:
                suggestions.append(ScalingSuggestion(
                    type="scale_up",
                    reason=f"Memory usage is at {usage_percent:.1f}%",
                    severity="warning" if usage_percent < 90 else "critical",
                    recommendation="Add more shards to distribute data",
                    params={"memory_usage_percent": usage_percent}
                ))

        if not suggestions:
            suggestions.append(ScalingSuggestion(
                type="none",
                reason="Cluster is healthy",
                severity="info",
                recommendation="No scaling actions needed",
                params={}
            ))

        return ScalingSuggestionsResponse(
            cluster_id=cluster_id,
            suggestions=suggestions,
            metrics=metrics
        )

    except ControllerAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Controller error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Failed to get suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Scaling Operations Routes ====================

@router.post("/failover", response_model=ControllerOperationResponse)
async def execute_failover(
    cluster_id: int,
    request: FailoverRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_EXECUTE]))
):
    """
    Execute shard failover via kvrocks-controller

    Promotes a slave to master in the specified shard.
    """
    cluster = await get_cluster_or_404(cluster_id, db)

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            result = await client.failover_shard(
                namespace=namespace,
                cluster=controller_cluster,
                shard_index=request.shard_index,
                preferred_node_id=request.preferred_node_id
            )

            # Log the operation
            task = ScalingTask(
                cluster_id=cluster_id,
                task_type=TaskType.FAILOVER,
                status=TaskStatus.COMPLETED,
                progress=100,
                params={
                    "shard_index": request.shard_index,
                    "preferred_node_id": request.preferred_node_id
                },
                created_by=current_user.id,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.add(task)
            await db.flush()  # Flush to get task.id

            log = ScalingTaskLog(
                task_id=task.id,
                level="info",
                message=f"Failover completed for shard {request.shard_index}"
            )
            db.add(log)
            await db.commit()

            return ControllerOperationResponse(
                success=True,
                message=f"Failover completed for shard {request.shard_index}",
                data=result
            )

    except ControllerAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failover failed: {e.message}"
        )


@router.post("/add-shard", response_model=ControllerOperationResponse)
async def add_shard(
    cluster_id: int,
    request: AddShardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_EXECUTE]))
):
    """
    Add a new shard to the cluster via kvrocks-controller

    First node in the list becomes master, others become slaves.
    """
    cluster = await get_cluster_or_404(cluster_id, db)

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            result = await client.create_shard(
                namespace=namespace,
                cluster=controller_cluster,
                nodes=request.nodes,
                password=request.password
            )

            # Log the operation
            task = ScalingTask(
                cluster_id=cluster_id,
                task_type=TaskType.ADD_SHARD,
                status=TaskStatus.COMPLETED,
                progress=100,
                params={"nodes": request.nodes},
                created_by=current_user.id,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.add(task)
            await db.commit()

            return ControllerOperationResponse(
                success=True,
                message="Shard added successfully",
                data=result
            )

    except ControllerAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to add shard: {e.message}"
        )


@router.post("/remove-shard", response_model=ControllerOperationResponse)
async def remove_shard(
    cluster_id: int,
    request: RemoveShardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_EXECUTE]))
):
    """
    Remove a shard from the cluster via kvrocks-controller

    Note: Slots must be migrated away before deletion.
    """
    cluster = await get_cluster_or_404(cluster_id, db)

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            # If target shard specified, migrate slots first
            if request.target_shard_index is not None:
                # Get current shard info
                shard = await client.get_shard(namespace, controller_cluster, request.shard_index)
                slot_ranges = shard.get("slotRanges", [])

                for sr in slot_ranges:
                    await client.migrate_slots(
                        namespace=namespace,
                        cluster=controller_cluster,
                        target_shard=request.target_shard_index,
                        slot_start=sr.get("start", 0),
                        slot_stop=sr.get("stop", 0)
                    )

            # Delete the shard
            await client.delete_shard(namespace, controller_cluster, request.shard_index)

            # Log the operation
            task = ScalingTask(
                cluster_id=cluster_id,
                task_type=TaskType.REMOVE_SHARD,
                status=TaskStatus.COMPLETED,
                progress=100,
                params={"shard_index": request.shard_index},
                created_by=current_user.id,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.add(task)
            await db.commit()

            return ControllerOperationResponse(
                success=True,
                message=f"Shard {request.shard_index} removed successfully"
            )

    except ControllerAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to remove shard: {e.message}"
        )


@router.post("/migrate-slots", response_model=ControllerOperationResponse)
async def migrate_slots(
    cluster_id: int,
    request: SlotMigrationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_EXECUTE]))
):
    """
    Migrate slots to target shard via kvrocks-controller

    The controller coordinates the migration process:
    1. Acquires cluster lock
    2. Initiates migration on source nodes
    3. Monitors migration status periodically
    4. Updates cluster metadata on completion
    """
    cluster = await get_cluster_or_404(cluster_id, db)

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            result = await client.migrate_slots(
                namespace=namespace,
                cluster=controller_cluster,
                target_shard=request.target_shard,
                slot_start=request.slot_start,
                slot_stop=request.slot_stop,
                slot_only=request.slot_only
            )

            # Log the operation
            task = ScalingTask(
                cluster_id=cluster_id,
                task_type=TaskType.SLOT_MIGRATION,
                status=TaskStatus.COMPLETED,
                progress=100,
                params={
                    "target_shard": request.target_shard,
                    "slot_start": request.slot_start,
                    "slot_stop": request.slot_stop
                },
                created_by=current_user.id,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.add(task)
            await db.commit()

            return ControllerOperationResponse(
                success=True,
                message=f"Slots {request.slot_start}-{request.slot_stop} migrated to shard {request.target_shard}",
                data={"version": result.get("version")}
            )

    except ControllerAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Migration failed: {e.message}"
        )


@router.post("/add-node", response_model=ControllerOperationResponse)
async def add_node(
    cluster_id: int,
    request: AddNodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_EXECUTE]))
):
    """Add a node to a shard via kvrocks-controller"""
    cluster = await get_cluster_or_404(cluster_id, db)

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            result = await client.create_node(
                namespace=namespace,
                cluster=controller_cluster,
                shard_index=request.shard_index,
                addr=request.addr,
                role=request.role,
                password=request.password
            )

            return ControllerOperationResponse(
                success=True,
                message=f"Node {request.addr} added to shard {request.shard_index}",
                data=result
            )

    except ControllerAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to add node: {e.message}"
        )


@router.post("/remove-node", response_model=ControllerOperationResponse)
async def remove_node(
    cluster_id: int,
    request: RemoveNodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_EXECUTE]))
):
    """Remove a node from a shard via kvrocks-controller"""
    cluster = await get_cluster_or_404(cluster_id, db)

    namespace = cluster.namespace or settings.KVROCKS_DEFAULT_NAMESPACE
    controller_cluster = cluster.controller_cluster_name or cluster.name

    try:
        async with get_controller_client(cluster) as client:
            await client.delete_node(
                namespace=namespace,
                cluster=controller_cluster,
                shard_index=request.shard_index,
                node_id=request.node_id
            )

            return ControllerOperationResponse(
                success=True,
                message=f"Node {request.node_id} removed from shard {request.shard_index}"
            )

    except ControllerAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to remove node: {e.message}"
        )


# ==================== Task Management Routes ====================

@router.get("/tasks", response_model=ScalingTaskListResponse)
async def list_tasks(
    cluster_id: int,
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_READ]))
):
    """List scaling tasks for a cluster"""
    await get_cluster_or_404(cluster_id, db)

    query = select(ScalingTask).where(ScalingTask.cluster_id == cluster_id)

    if status:
        query = query.where(ScalingTask.status == status)
    if task_type:
        query = query.where(ScalingTask.task_type == task_type)

    # Count total
    count_query = select(ScalingTask.id).where(ScalingTask.cluster_id == cluster_id)
    if status:
        count_query = count_query.where(ScalingTask.status == status)
    if task_type:
        count_query = count_query.where(ScalingTask.task_type == task_type)

    result = await db.execute(count_query)
    total = len(result.all())

    # Get paginated results
    query = query.order_by(desc(ScalingTask.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    tasks = result.scalars().all()

    return ScalingTaskListResponse(
        tasks=[ScalingTaskResponse.model_validate(t) for t in tasks],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/tasks/{task_id}", response_model=ScalingTaskDetail)
async def get_task(
    cluster_id: int,
    task_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_READ]))
):
    """Get scaling task details"""
    task = await get_task_or_404(task_id, cluster_id, db)

    return ScalingTaskDetail(
        id=task.id,
        cluster_id=task.cluster_id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        current_step=task.current_step,
        error_message=task.error_message,
        error_detail=task.error_detail,
        can_rollback=task.can_rollback,
        created_by=task.created_by,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        updated_at=task.updated_at,
        params=task.params or {},
        rollback_data=task.rollback_data or {},
        subtasks=[ScalingSubtaskResponse.model_validate(st) for st in task.subtasks],
        logs=[ScalingTaskLogResponse.model_validate(log) for log in task.logs[-100:]]
    )


@router.get("/tasks/{task_id}/logs", response_model=List[ScalingTaskLogResponse])
async def get_task_logs(
    cluster_id: int,
    task_id: int,
    level: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.SCALING_READ]))
):
    """Get logs for a scaling task"""
    await get_task_or_404(task_id, cluster_id, db)

    query = select(ScalingTaskLog).where(ScalingTaskLog.task_id == task_id)

    if level:
        query = query.where(ScalingTaskLog.level == level)

    query = query.order_by(desc(ScalingTaskLog.created_at)).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [ScalingTaskLogResponse.model_validate(log) for log in logs]
