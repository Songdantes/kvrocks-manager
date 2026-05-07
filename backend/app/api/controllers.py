"""
KVrocks Controller management API routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
import logging

from app.database import get_db
from app.models import KVrocksController, ControllerStatus, Cluster, ClusterType, ClusterStatus, Node, NodeRole, NodeStatus
from app.schemas.controller import (
    ControllerCreate, ControllerUpdate, ImportClustersRequest,
    ControllerResponse, ControllerDetail, DiscoverResponse, DiscoveredNamespace,
    ControllerCheckResponse, ImportClustersResponse, ImportResult
)
from app.services.controller import AsyncKVrocksControllerClient, ControllerAPIError
from app.core.security import get_current_user
from app.core.permissions import PermissionChecker, Permissions
from app.models import User

router = APIRouter(prefix="/controllers", tags=["Controllers"])
logger = logging.getLogger(__name__)


def _build_controller_response(ctrl: KVrocksController, cluster_count: int = None) -> ControllerResponse:
    """Build controller response from model"""
    # Use provided cluster_count or try to get from relationship (if loaded)
    if cluster_count is None:
        try:
            cluster_count = len(ctrl.clusters) if ctrl.clusters else 0
        except Exception:
            cluster_count = 0

    return ControllerResponse(
        id=ctrl.id,
        name=ctrl.name,
        address=ctrl.address,
        status=ctrl.status,
        version=ctrl.version,
        description=ctrl.description,
        cluster_count=cluster_count,
        last_check_at=ctrl.last_check_at,
        created_at=ctrl.created_at,
        updated_at=ctrl.updated_at
    )


@router.get("", response_model=List[ControllerResponse])
async def list_controllers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status_filter: Optional[ControllerStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all controllers"""
    query = select(KVrocksController).options(selectinload(KVrocksController.clusters))

    if search:
        query = query.where(
            KVrocksController.name.contains(search) |
            KVrocksController.address.contains(search)
        )
    if status_filter:
        query = query.where(KVrocksController.status == status_filter)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    controllers = result.scalars().all()

    logger.info(f"Found {len(controllers)} controllers")
    for ctrl in controllers:
        logger.info(f"Controller: id={ctrl.id}, name={ctrl.name}, address={ctrl.address}")

    return [_build_controller_response(ctrl) for ctrl in controllers]


@router.post("", response_model=ControllerResponse, status_code=status.HTTP_201_CREATED)
async def create_controller(
    data: ControllerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.CLUSTER_CREATE]))
):
    """Add a new controller"""
    # Check if address already exists
    existing = await db.execute(
        select(KVrocksController).where(KVrocksController.address == data.address)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Controller with address {data.address} already exists"
        )

    # Test connection
    controller_status = ControllerStatus.UNKNOWN
    version = None
    last_error = None

    try:
        async with AsyncKVrocksControllerClient(data.address) as client:
            if await client.health_check():
                controller_status = ControllerStatus.ONLINE
                # Try to get version from any namespace/cluster info
                try:
                    namespaces = await client.list_namespaces()
                    version = f"namespaces: {len(namespaces)}"
                except Exception:
                    pass
            else:
                controller_status = ControllerStatus.OFFLINE
    except ControllerAPIError as e:
        controller_status = ControllerStatus.ERROR
        last_error = str(e)
    except Exception as e:
        controller_status = ControllerStatus.ERROR
        last_error = str(e)

    controller = KVrocksController(
        name=data.name,
        address=data.address,
        description=data.description,
        status=controller_status,
        version=version,
        last_check_at=datetime.utcnow(),
        last_error=last_error
    )

    db.add(controller)
    await db.commit()
    await db.refresh(controller)

    # New controller has no clusters yet
    return _build_controller_response(controller, cluster_count=0)


@router.get("/{controller_id}", response_model=ControllerDetail)
async def get_controller(
    controller_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get controller details"""
    result = await db.execute(
        select(KVrocksController)
        .options(selectinload(KVrocksController.clusters))
        .where(KVrocksController.id == controller_id)
    )
    controller = result.scalar_one_or_none()

    if not controller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    clusters_data = []
    for c in controller.clusters:
        clusters_data.append({
            "id": c.id,
            "name": c.name,
            "namespace": c.namespace,
            "controller_cluster_name": c.controller_cluster_name,
            "status": c.status.value if c.status else None,
            "node_count": c.node_count
        })

    return ControllerDetail(
        id=controller.id,
        name=controller.name,
        address=controller.address,
        status=controller.status,
        version=controller.version,
        description=controller.description,
        cluster_count=len(controller.clusters),
        last_check_at=controller.last_check_at,
        last_error=controller.last_error,
        created_at=controller.created_at,
        updated_at=controller.updated_at,
        clusters=clusters_data
    )


@router.put("/{controller_id}", response_model=ControllerResponse)
async def update_controller(
    controller_id: int,
    data: ControllerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.CLUSTER_UPDATE]))
):
    """Update controller info"""
    result = await db.execute(
        select(KVrocksController)
        .options(selectinload(KVrocksController.clusters))
        .where(KVrocksController.id == controller_id)
    )
    controller = result.scalar_one_or_none()

    if not controller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    if data.name is not None:
        controller.name = data.name
    if data.description is not None:
        controller.description = data.description

    await db.commit()
    await db.refresh(controller)

    return _build_controller_response(controller)


@router.delete("/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_controller(
    controller_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.CLUSTER_DELETE]))
):
    """Delete a controller"""
    result = await db.execute(
        select(KVrocksController)
        .options(selectinload(KVrocksController.clusters))
        .where(KVrocksController.id == controller_id)
    )
    controller = result.scalar_one_or_none()

    if not controller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    # Unlink clusters (don't delete them, just remove association)
    for cluster in controller.clusters:
        cluster.controller_id = None
        cluster.controller_managed = False

    await db.delete(controller)
    await db.commit()


@router.post("/{controller_id}/check", response_model=ControllerCheckResponse)
async def check_controller(
    controller_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check controller health status"""
    result = await db.execute(
        select(KVrocksController).where(KVrocksController.id == controller_id)
    )
    controller = result.scalar_one_or_none()

    if not controller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    try:
        async with AsyncKVrocksControllerClient(controller.address) as client:
            healthy = await client.health_check()
            if healthy:
                controller.status = ControllerStatus.ONLINE
                controller.last_error = None
                # Count namespaces
                try:
                    namespaces = await client.list_namespaces()
                    controller.version = f"namespaces: {len(namespaces)}"
                except Exception:
                    pass
            else:
                controller.status = ControllerStatus.OFFLINE
                controller.last_error = "Health check failed"

            controller.last_check_at = datetime.utcnow()
            await db.commit()

            return ControllerCheckResponse(
                success=healthy,
                status=controller.status,
                version=controller.version
            )

    except ControllerAPIError as e:
        controller.status = ControllerStatus.ERROR
        controller.last_error = str(e)
        controller.last_check_at = datetime.utcnow()
        await db.commit()

        return ControllerCheckResponse(
            success=False,
            status=ControllerStatus.ERROR,
            error=str(e)
        )
    except Exception as e:
        controller.status = ControllerStatus.ERROR
        controller.last_error = str(e)
        controller.last_check_at = datetime.utcnow()
        await db.commit()

        return ControllerCheckResponse(
            success=False,
            status=ControllerStatus.ERROR,
            error=str(e)
        )


@router.get("/{controller_id}/discover", response_model=DiscoverResponse)
async def discover_clusters(
    controller_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Discover namespaces and clusters from controller"""
    result = await db.execute(
        select(KVrocksController).where(KVrocksController.id == controller_id)
    )
    controller = result.scalar_one_or_none()

    if not controller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    try:
        async with AsyncKVrocksControllerClient(controller.address) as client:
            namespaces_list = await client.list_namespaces()

            discovered = []
            total_clusters = 0

            for ns in namespaces_list:
                try:
                    clusters = await client.list_clusters(ns)
                    discovered.append(DiscoveredNamespace(
                        namespace=ns,
                        clusters=clusters
                    ))
                    total_clusters += len(clusters)
                except ControllerAPIError as e:
                    logger.warning(f"Failed to list clusters in namespace {ns}: {e}")
                    discovered.append(DiscoveredNamespace(
                        namespace=ns,
                        clusters=[]
                    ))

            # Update controller status
            controller.status = ControllerStatus.ONLINE
            controller.last_check_at = datetime.utcnow()
            controller.last_error = None
            await db.commit()

            return DiscoverResponse(
                controller_id=controller_id,
                address=controller.address,
                namespaces=discovered,
                total_clusters=total_clusters
            )

    except ControllerAPIError as e:
        controller.status = ControllerStatus.ERROR
        controller.last_error = str(e)
        controller.last_check_at = datetime.utcnow()
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to controller: {e}"
        )
    except Exception as e:
        controller.status = ControllerStatus.ERROR
        controller.last_error = str(e)
        controller.last_check_at = datetime.utcnow()
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to controller: {e}"
        )


@router.post("/{controller_id}/import", response_model=ImportClustersResponse)
async def import_clusters(
    controller_id: int,
    data: ImportClustersRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.CLUSTER_CREATE]))
):
    """Import selected clusters from controller"""
    result = await db.execute(
        select(KVrocksController).where(KVrocksController.id == controller_id)
    )
    controller = result.scalar_one_or_none()

    if not controller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Controller not found"
        )

    results = []
    imported_count = 0
    failed_count = 0

    try:
        async with AsyncKVrocksControllerClient(controller.address) as client:
            for cluster_info in data.clusters:
                namespace = cluster_info.get("namespace")
                cluster_name = cluster_info.get("cluster")

                if not namespace or not cluster_name:
                    results.append(ImportResult(
                        namespace=namespace or "",
                        cluster=cluster_name or "",
                        success=False,
                        error="Missing namespace or cluster name"
                    ))
                    failed_count += 1
                    continue

                try:
                    # Check if cluster already imported
                    existing = await db.execute(
                        select(Cluster).where(
                            Cluster.controller_id == controller_id,
                            Cluster.namespace == namespace,
                            Cluster.controller_cluster_name == cluster_name
                        )
                    )
                    if existing.scalar_one_or_none():
                        results.append(ImportResult(
                            namespace=namespace,
                            cluster=cluster_name,
                            success=False,
                            error="Cluster already imported"
                        ))
                        failed_count += 1
                        continue

                    # Get cluster topology from controller
                    cluster_data = await client.get_cluster(namespace, cluster_name)
                    logger.info(f"Importing cluster {namespace}/{cluster_name}: {cluster_data}")

                    # Create cluster record
                    cluster = Cluster(
                        name=cluster_name,
                        cluster_type=ClusterType.SHARDING,
                        status=ClusterStatus.RUNNING,
                        description=f"Imported from {controller.name}",
                        owner_id=current_user.id,
                        controller_id=controller_id,
                        namespace=namespace,
                        controller_cluster_name=cluster_name,
                        controller_managed=True,
                        controller_version=cluster_data.get("version", 0)
                    )

                    db.add(cluster)
                    await db.flush()  # Get cluster.id

                    # Import nodes from shards
                    shards = cluster_data.get("shards", [])
                    for shard_idx, shard in enumerate(shards):
                        nodes = shard.get("nodes", [])
                        slot_ranges = shard.get("slot_ranges") or shard.get("slotRanges", [])

                        # Build slot range string
                        slots_str_parts = []
                        for sr in slot_ranges:
                            if isinstance(sr, str):
                                slots_str_parts.append(sr)
                            else:
                                start = sr.get("start", 0)
                                stop = sr.get("stop", 0)
                                if start == stop:
                                    slots_str_parts.append(str(start))
                                else:
                                    slots_str_parts.append(f"{start}-{stop}")
                        slots_str = ",".join(slots_str_parts)

                        for node_data in nodes:
                            addr = node_data.get("addr", "")
                            if ":" in addr:
                                host, port_str = addr.rsplit(":", 1)
                                port = int(port_str)
                            else:
                                host = addr
                                port = 6379

                            role_str = node_data.get("role", "slave").lower()
                            role = NodeRole.MASTER if role_str == "master" else NodeRole.SLAVE

                            node = Node(
                                cluster_id=cluster.id,
                                host=host,
                                port=port,
                                password=node_data.get("password"),
                                role=role,
                                status=NodeStatus.RUNNING,
                                cluster_node_id=node_data.get("id"),
                                shard_index=shard_idx,
                                slots_range=slots_str if role == NodeRole.MASTER else None
                            )
                            db.add(node)

                    # Grant access to current user
                    from app.models.user import user_clusters
                    await db.execute(
                        user_clusters.insert().values(user_id=current_user.id, cluster_id=cluster.id)
                    )

                    results.append(ImportResult(
                        namespace=namespace,
                        cluster=cluster_name,
                        success=True,
                        cluster_id=cluster.id
                    ))
                    imported_count += 1

                except ControllerAPIError as e:
                    logger.error(f"Failed to import cluster {namespace}/{cluster_name}: {e}")
                    results.append(ImportResult(
                        namespace=namespace,
                        cluster=cluster_name,
                        success=False,
                        error=str(e)
                    ))
                    failed_count += 1
                except Exception as e:
                    logger.error(f"Failed to import cluster {namespace}/{cluster_name}: {e}")
                    results.append(ImportResult(
                        namespace=namespace,
                        cluster=cluster_name,
                        success=False,
                        error=str(e)
                    ))
                    failed_count += 1

        await db.commit()

        return ImportClustersResponse(
            controller_id=controller_id,
            results=results,
            imported_count=imported_count,
            failed_count=failed_count
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {e}"
        )
