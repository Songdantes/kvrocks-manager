"""
Cluster management API routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.database import get_db
from app.models import Cluster, Node, ClusterStatus, NodeStatus, ClusterType
from app.schemas import (
    ClusterCreate, ClusterUpdate, ClusterResponse, ClusterDetail,
    NodeCreate, NodeUpdate, NodeResponse, NodeDetail,
    NodeConfigUpdate, CommandRequest, CommandResponse, NodeInfoResponse,
    BatchNodeIds, BatchOperationResult
)
from app.services.kvrocks import create_kvrocks_client
from app.core.security import get_current_user
from app.core.permissions import PermissionChecker, Permissions
from app.models import User
import json

router = APIRouter(prefix="/clusters", tags=["Clusters"])
node_router = APIRouter(prefix="/nodes", tags=["Nodes"])


# ==================== Cluster Routes ====================

@router.get("", response_model=List[ClusterResponse])
async def list_clusters(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    cluster_type: Optional[ClusterType] = None,
    status: Optional[ClusterStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all clusters"""
    query = select(Cluster).options(selectinload(Cluster.nodes), selectinload(Cluster.controller))

    if search:
        query = query.where(Cluster.name.contains(search))
    if cluster_type:
        query = query.where(Cluster.cluster_type == cluster_type)
    if status:
        query = query.where(Cluster.status == status)

    # Data-level permission: filter by user's accessible clusters
    # Super admin or users with cluster:read can see all clusters
    is_super_admin = any(r.name == 'super_admin' for r in current_user.roles)
    has_cluster_read = 'cluster:read' in (current_user.permissions or [])
    if not is_super_admin and not has_cluster_read:
        # Only show clusters the user has access to
        query = query.where(Cluster.id.in_(
            select(Cluster.id).join(Cluster.users).where(User.id == current_user.id)
        ))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    clusters = result.scalars().all()

    return [
        ClusterResponse(
            id=c.id,
            name=c.name,
            cluster_type=c.cluster_type,
            status=c.status,
            description=c.description,
            owner_id=c.owner_id,
            controller_id=c.controller_id,
            controller_name=c.controller.name if c.controller else None,
            created_at=c.created_at,
            updated_at=c.updated_at,
            node_count=c.node_count,
            master_count=c.master_count,
            slave_count=c.slave_count
        )
        for c in clusters
    ]


@router.post("", response_model=ClusterResponse, status_code=status.HTTP_201_CREATED)
async def create_cluster(
    cluster_data: ClusterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker([Permissions.CLUSTER_CREATE]))
):
    """Create a new cluster"""
    # Verify controller exists if specified
    if cluster_data.controller_id:
        from app.models.kvrocks_controller import KVrocksController
        result = await db.execute(
            select(KVrocksController).where(KVrocksController.id == cluster_data.controller_id)
        )
        controller = result.scalar_one_or_none()
        if not controller:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Controller not found"
            )

    cluster = Cluster(
        name=cluster_data.name,
        cluster_type=cluster_data.cluster_type,
        description=cluster_data.description,
        owner_id=current_user.id,
        controller_id=cluster_data.controller_id,
        status=ClusterStatus.STOPPED
    )

    db.add(cluster)
    await db.commit()
    await db.refresh(cluster)

    # Grant access to the creator
    from app.models.user import user_clusters
    await db.execute(
        user_clusters.insert().values(user_id=current_user.id, cluster_id=cluster.id)
    )
    await db.commit()

    return ClusterResponse(
        id=cluster.id,
        name=cluster.name,
        cluster_type=cluster.cluster_type,
        status=cluster.status,
        description=cluster.description,
        owner_id=cluster.owner_id,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        node_count=0,
        master_count=0,
        slave_count=0
    )


@router.get("/{cluster_id}", response_model=ClusterDetail)
async def get_cluster(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.CLUSTER_READ]))
):
    """Get cluster details"""
    result = await db.execute(
        select(Cluster)
        .options(selectinload(Cluster.nodes))
        .where(Cluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    return ClusterDetail(
        id=cluster.id,
        name=cluster.name,
        cluster_type=cluster.cluster_type,
        status=cluster.status,
        description=cluster.description,
        owner_id=cluster.owner_id,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        node_count=cluster.node_count,
        master_count=cluster.master_count,
        slave_count=cluster.slave_count,
        nodes=[
            NodeResponse(
                id=n.id,
                cluster_id=n.cluster_id,
                host=n.host,
                port=n.port,
                password=None,  # Don't expose password
                role=n.role,
                status=n.status,
                master_node_id=n.master_node_id,
                created_at=n.created_at,
                updated_at=n.updated_at
            )
            for n in cluster.nodes
        ]
    )


@router.put("/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: int,
    cluster_data: ClusterUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.CLUSTER_UPDATE]))
):
    """Update a cluster"""
    result = await db.execute(
        select(Cluster)
        .options(selectinload(Cluster.nodes))
        .where(Cluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    if cluster_data.name is not None:
        cluster.name = cluster_data.name
    if cluster_data.description is not None:
        cluster.description = cluster_data.description

    await db.commit()
    await db.refresh(cluster)

    return ClusterResponse(
        id=cluster.id,
        name=cluster.name,
        cluster_type=cluster.cluster_type,
        status=cluster.status,
        description=cluster.description,
        owner_id=cluster.owner_id,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        node_count=cluster.node_count,
        master_count=cluster.master_count,
        slave_count=cluster.slave_count
    )


@router.delete("/{cluster_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cluster(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.CLUSTER_DELETE]))
):
    """Delete a cluster"""
    result = await db.execute(
        select(Cluster).where(Cluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    # Check if cluster is running
    if cluster.status == ClusterStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a running cluster. Stop it first."
        )

    await db.delete(cluster)
    await db.commit()


@router.post("/{cluster_id}/refresh-status")
async def refresh_cluster_status(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.CLUSTER_READ]))
):
    """Refresh cluster and node status by pinging all nodes"""
    result = await db.execute(
        select(Cluster)
        .options(selectinload(Cluster.nodes))
        .where(Cluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    running_nodes = 0
    error_nodes = 0

    for node in cluster.nodes:
        client = create_kvrocks_client(node.host, node.port, node.password)
        try:
            if client.ping():
                node.status = NodeStatus.RUNNING
                running_nodes += 1
            else:
                node.status = NodeStatus.ERROR
                error_nodes += 1
        except Exception:
            node.status = NodeStatus.ERROR
            error_nodes += 1
        finally:
            client.close()

    # Update cluster status based on nodes
    if running_nodes == len(cluster.nodes) and running_nodes > 0:
        cluster.status = ClusterStatus.RUNNING
    elif running_nodes > 0:
        cluster.status = ClusterStatus.RUNNING  # Partially running
    elif error_nodes > 0:
        cluster.status = ClusterStatus.ERROR
    else:
        cluster.status = ClusterStatus.STOPPED

    await db.commit()

    return {
        "cluster_status": cluster.status,
        "running_nodes": running_nodes,
        "error_nodes": error_nodes,
        "total_nodes": len(cluster.nodes)
    }


# ==================== Node Routes ====================

@node_router.get("", response_model=List[NodeResponse])
async def list_nodes(
    cluster_id: Optional[int] = None,
    status: Optional[NodeStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.NODE_READ]))
):
    """List nodes"""
    query = select(Node)

    if cluster_id:
        query = query.where(Node.cluster_id == cluster_id)
    if status:
        query = query.where(Node.status == status)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    nodes = result.scalars().all()

    return [
        NodeResponse(
            id=n.id,
            cluster_id=n.cluster_id,
            host=n.host,
            port=n.port,
            password=None,
            role=n.role,
            status=n.status,
            master_node_id=n.master_node_id,
            created_at=n.created_at,
            updated_at=n.updated_at
        )
        for n in nodes
    ]


@node_router.post("", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(
    node_data: NodeCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.NODE_CREATE]))
):
    """Add a new node to a cluster"""
    # Check if cluster exists
    result = await db.execute(
        select(Cluster).where(Cluster.id == node_data.cluster_id)
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    # Check if node already exists
    existing = await db.execute(
        select(Node).where(
            Node.host == node_data.host,
            Node.port == node_data.port
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Node {node_data.host}:{node_data.port} already exists"
        )

    # Test connection
    client = create_kvrocks_client(node_data.host, node_data.port, node_data.password)
    try:
        if not client.ping():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot connect to {node_data.host}:{node_data.port}"
            )
        initial_status = NodeStatus.RUNNING
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot connect to {node_data.host}:{node_data.port}: {str(e)}"
        )
    finally:
        client.close()

    node = Node(
        cluster_id=node_data.cluster_id,
        host=node_data.host,
        port=node_data.port,
        password=node_data.password,
        role=node_data.role,
        master_node_id=node_data.master_node_id,
        status=initial_status
    )

    db.add(node)
    await db.commit()
    await db.refresh(node)

    return NodeResponse(
        id=node.id,
        cluster_id=node.cluster_id,
        host=node.host,
        port=node.port,
        password=None,
        role=node.role,
        status=node.status,
        master_node_id=node.master_node_id,
        created_at=node.created_at,
        updated_at=node.updated_at
    )


@node_router.get("/{node_id}", response_model=NodeDetail)
async def get_node(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.NODE_READ]))
):
    """Get node details"""
    result = await db.execute(
        select(Node)
        .options(selectinload(Node.configs), selectinload(Node.cluster))
        .where(Node.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found"
        )

    return NodeDetail(
        id=node.id,
        cluster_id=node.cluster_id,
        host=node.host,
        port=node.port,
        password=None,
        role=node.role,
        status=node.status,
        master_node_id=node.master_node_id,
        created_at=node.created_at,
        updated_at=node.updated_at,
        configs=[
            {"config_key": c.config_key, "config_value": c.config_value, "updated_at": c.updated_at}
            for c in node.configs
        ],
        cluster_name=node.cluster.name if node.cluster else None
    )


@node_router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.NODE_DELETE]))
):
    """Delete a node"""
    result = await db.execute(
        select(Node).where(Node.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found"
        )

    await db.delete(node)
    await db.commit()


@node_router.get("/{node_id}/info", response_model=NodeInfoResponse)
async def get_node_info(
    node_id: int,
    section: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.NODE_READ]))
):
    """Get KVrocks INFO from a node"""
    result = await db.execute(
        select(Node).where(Node.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found"
        )

    client = create_kvrocks_client(node.host, node.port, node.password)
    try:
        info = client.info(section)
        return NodeInfoResponse(success=True, info=info)
    except Exception as e:
        return NodeInfoResponse(success=False, error=str(e))
    finally:
        client.close()


@node_router.get("/{node_id}/config")
async def get_node_config(
    node_id: int,
    pattern: str = "*",
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.CONFIG_READ]))
):
    """Get KVrocks configuration from a node"""
    result = await db.execute(
        select(Node).where(Node.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found"
        )

    client = create_kvrocks_client(node.host, node.port, node.password)
    try:
        config = client.config_get(pattern)
        return {"success": True, "config": config}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        client.close()


@node_router.put("/{node_id}/config")
async def update_node_config(
    node_id: int,
    config_data: NodeConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.CONFIG_UPDATE]))
):
    """Update KVrocks configuration on a node"""
    result = await db.execute(
        select(Node).where(Node.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found"
        )

    client = create_kvrocks_client(node.host, node.port, node.password)
    try:
        results = {}
        for key, value in config_data.configs.items():
            try:
                client.config_set(key, value)
                results[key] = {"success": True}
            except Exception as e:
                results[key] = {"success": False, "error": str(e)}

        return {"success": True, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        client.close()


@node_router.post("/{node_id}/command", response_model=CommandResponse)
async def execute_command(
    node_id: int,
    command_data: CommandRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.COMMAND_EXECUTE]))
):
    """Execute a command on a node"""
    result = await db.execute(
        select(Node).where(Node.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found"
        )

    # Block dangerous commands
    dangerous_commands = ['FLUSHALL', 'FLUSHDB', 'SHUTDOWN', 'DEBUG', 'SLAVEOF', 'REPLICAOF']
    cmd_upper = command_data.command.upper()
    if cmd_upper in dangerous_commands:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Command '{command_data.command}' is not allowed"
        )

    client = create_kvrocks_client(node.host, node.port, node.password)
    try:
        if command_data.args:
            result = client.execute_command(command_data.command, *command_data.args)
        else:
            result = client.execute_command(command_data.command)
        return CommandResponse(success=True, result=result)
    except Exception as e:
        return CommandResponse(success=False, result=None, error=str(e))
    finally:
        client.close()


@node_router.post("/{node_id}/ping")
async def ping_node(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(PermissionChecker([Permissions.NODE_READ]))
):
    """Ping a node to check if it's alive"""
    result = await db.execute(
        select(Node).where(Node.id == node_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found"
        )

    client = create_kvrocks_client(node.host, node.port, node.password)
    try:
        alive = client.ping()
        if alive:
            node.status = NodeStatus.RUNNING
        else:
            node.status = NodeStatus.ERROR
        await db.commit()
        return {"alive": alive, "status": node.status}
    except Exception as e:
        node.status = NodeStatus.ERROR
        await db.commit()
        return {"alive": False, "status": node.status, "error": str(e)}
    finally:
        client.close()
