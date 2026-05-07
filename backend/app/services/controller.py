"""
KVrocks Controller client service

Based on Apache kvrocks-controller project:
https://github.com/apache/kvrocks-controller

The controller uses a centralized management model instead of Redis's gossip protocol.
API endpoints follow: /api/v1/namespaces/{namespace}/clusters/{cluster}/...
"""
import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SlotRange:
    """Slot range representation"""
    start: int
    stop: int

    def to_dict(self) -> Dict:
        return {"start": self.start, "stop": self.stop}


@dataclass
class Node:
    """Cluster node representation"""
    id: str
    addr: str
    role: str  # "master" or "slave"
    password: Optional[str] = None


@dataclass
class Shard:
    """Cluster shard representation"""
    nodes: List[Node]
    slot_ranges: List[SlotRange]
    migrating_slot: Optional[int] = None
    target_shard_index: Optional[int] = None


@dataclass
class Cluster:
    """Cluster representation"""
    name: str
    version: int
    shards: List[Shard]


class KVrocksControllerClient:
    """
    Client for Apache kvrocks-controller HTTP API

    The controller manages KVrocks clusters with:
    - Namespace: logical grouping for multi-tenancy
    - Cluster: a KVrocks cluster
    - Shard: a group of nodes (1 master + N slaves) handling a slot range
    - Node: individual KVrocks instance
    """

    def __init__(
        self,
        controller_url: str,
        timeout: int = 30,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize controller client

        Args:
            controller_url: Base URL of kvrocks-controller, e.g., "http://localhost:9379"
            timeout: Request timeout in seconds
            username: Optional basic auth username
            password: Optional basic auth password
        """
        self.base_url = controller_url.rstrip('/')
        self.timeout = timeout
        self.auth = (username, password) if username and password else None
        self._client = None

    @property
    def client(self) -> httpx.Client:
        """Lazy initialization of HTTP client"""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                auth=self.auth
            )
        return self._client

    def close(self):
        """Close the HTTP client"""
        if self._client:
            self._client.close()
            self._client = None

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to controller"""
        try:
            response = self.client.request(method, path, **kwargs)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {}
        except httpx.HTTPStatusError as e:
            logger.error(f"Controller API error: {e.response.status_code} - {e.response.text}")
            raise ControllerAPIError(
                f"API request failed: {e.response.status_code}",
                status_code=e.response.status_code,
                detail=e.response.text
            )
        except Exception as e:
            logger.error(f"Controller request failed: {e}")
            raise ControllerAPIError(f"Request failed: {str(e)}")

    # ==================== Namespace API ====================

    def list_namespaces(self) -> List[str]:
        """List all namespaces"""
        result = self._request("GET", "/api/v1/namespaces")
        # Controller returns {"data": {"namespaces": [...]}}
        data = result.get("data", result)
        return data.get("namespaces", [])

    def create_namespace(self, namespace: str) -> Dict:
        """Create a new namespace"""
        return self._request("POST", "/api/v1/namespaces", json={"namespace": namespace})

    def delete_namespace(self, namespace: str) -> bool:
        """Delete a namespace"""
        self._request("DELETE", f"/api/v1/namespaces/{namespace}")
        return True

    def namespace_exists(self, namespace: str) -> bool:
        """Check if namespace exists"""
        try:
            self._request("GET", f"/api/v1/namespaces/{namespace}")
            return True
        except ControllerAPIError as e:
            if e.status_code == 404:
                return False
            raise

    # ==================== Cluster API ====================

    def list_clusters(self, namespace: str) -> List[str]:
        """List clusters in a namespace"""
        result = self._request("GET", f"/api/v1/namespaces/{namespace}/clusters")
        # Controller returns {"data": {"clusters": [...]}}
        data = result.get("data", result)
        return data.get("clusters", [])

    def get_cluster(self, namespace: str, cluster: str) -> Dict[str, Any]:
        """Get cluster details"""
        result = self._request("GET", f"/api/v1/namespaces/{namespace}/clusters/{cluster}")
        # Controller returns {"data": {"cluster": {...}}}
        data = result.get("data", result)
        return data.get("cluster", data)

    def create_cluster(
        self,
        namespace: str,
        cluster_name: str,
        nodes: List[str],
        replicas: int = 0,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new cluster

        Args:
            namespace: Namespace name
            cluster_name: Cluster name
            nodes: List of node addresses (e.g., ["127.0.0.1:6666", "127.0.0.1:6667"])
            replicas: Number of replicas per master (default 0)
            password: Optional cluster password

        Returns:
            Created cluster object
        """
        data = {
            "name": cluster_name,
            "nodes": nodes,
            "replicas": replicas
        }
        if password:
            data["password"] = password

        result = self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/clusters",
            json=data
        )
        return result.get("cluster", result)

    def import_cluster(
        self,
        namespace: str,
        cluster_name: str,
        nodes: List[str],
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Import an existing cluster

        The controller will connect to the nodes and discover the cluster topology.

        Args:
            namespace: Namespace name
            cluster_name: Cluster name
            nodes: List of node addresses to discover from
            password: Optional cluster password
        """
        data = {"nodes": nodes}
        if password:
            data["password"] = password

        result = self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster_name}/import",
            json=data
        )
        return result.get("cluster", result)

    def delete_cluster(self, namespace: str, cluster: str) -> bool:
        """Delete a cluster"""
        self._request("DELETE", f"/api/v1/namespaces/{namespace}/clusters/{cluster}")
        return True

    # ==================== Shard API ====================

    def list_shards(self, namespace: str, cluster: str) -> List[Dict]:
        """List shards in a cluster"""
        result = self._request(
            "GET",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards"
        )
        return result.get("shards", [])

    def get_shard(self, namespace: str, cluster: str, shard_index: int) -> Dict[str, Any]:
        """Get shard details"""
        result = self._request(
            "GET",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}"
        )
        return result.get("shard", {})

    def create_shard(
        self,
        namespace: str,
        cluster: str,
        nodes: List[str],
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new shard (add shard to cluster)

        First node becomes master, others become slaves.

        Args:
            namespace: Namespace name
            cluster: Cluster name
            nodes: List of node addresses for the new shard
            password: Optional password for the nodes
        """
        data = {"nodes": nodes}
        if password:
            data["password"] = password

        result = self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards",
            json=data
        )
        return result.get("shard", result)

    def delete_shard(self, namespace: str, cluster: str, shard_index: int) -> bool:
        """
        Delete a shard from the cluster

        Note: Slots must be migrated away before deletion.
        """
        self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}"
        )
        return True

    def failover_shard(
        self,
        namespace: str,
        cluster: str,
        shard_index: int,
        preferred_node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger failover for a shard

        Promotes a slave to master. If preferred_node_id is not specified,
        the controller will select the healthiest replica.

        Args:
            namespace: Namespace name
            cluster: Cluster name
            shard_index: Index of the shard to failover
            preferred_node_id: Optional preferred node to promote
        """
        data = {}
        if preferred_node_id:
            data["preferred_node_id"] = preferred_node_id

        result = self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}/failover",
            json=data
        )
        return result

    # ==================== Node API ====================

    def list_nodes(self, namespace: str, cluster: str, shard_index: int) -> List[Dict]:
        """List nodes in a shard"""
        result = self._request(
            "GET",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}/nodes"
        )
        return result.get("nodes", [])

    def create_node(
        self,
        namespace: str,
        cluster: str,
        shard_index: int,
        addr: str,
        role: str = "slave",
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a node to a shard

        Args:
            namespace: Namespace name
            cluster: Cluster name
            shard_index: Shard index to add node to
            addr: Node address (host:port)
            role: Node role ("master" or "slave", default "slave")
            password: Optional password for the node
        """
        data = {
            "addr": addr,
            "role": role
        }
        if password:
            data["password"] = password

        result = self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}/nodes",
            json=data
        )
        return result

    def delete_node(
        self,
        namespace: str,
        cluster: str,
        shard_index: int,
        node_id: str
    ) -> bool:
        """Delete a node from a shard"""
        self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}/nodes/{node_id}"
        )
        return True

    # ==================== Migration API ====================

    def migrate_slots(
        self,
        namespace: str,
        cluster: str,
        target_shard: int,
        slot_start: int,
        slot_stop: int,
        slot_only: bool = False
    ) -> Dict[str, Any]:
        """
        Migrate slots to target shard

        The controller coordinates the migration process:
        1. Acquires cluster lock
        2. Initiates migration on source nodes
        3. Monitors migration status periodically
        4. Updates cluster metadata on completion

        Args:
            namespace: Namespace name
            cluster: Cluster name
            target_shard: Target shard index
            slot_start: Start of slot range
            slot_stop: End of slot range (inclusive)
            slot_only: If True, only migrate slot metadata without data

        Returns:
            Updated cluster object
        """
        # Controller expects slot as string format "start-stop" or "slot"
        if slot_start == slot_stop:
            slot_str = str(slot_start)
        else:
            slot_str = f"{slot_start}-{slot_stop}"

        data = {
            "target": target_shard,
            "slot": slot_str,
            "slot_only": slot_only
        }

        result = self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/migrate",
            json=data
        )
        return result.get("cluster", result)

    # ==================== Utility Methods ====================

    def get_cluster_topology(self, namespace: str, cluster: str) -> Dict[str, Any]:
        """
        Get complete cluster topology

        Returns cluster with all shards, nodes, and slot distribution.
        """
        cluster_info = self.get_cluster(namespace, cluster)

        # Calculate slot statistics
        total_slots = 0
        for shard in cluster_info.get("shards", []):
            for slot_range in shard.get("slotRanges", []):
                total_slots += slot_range["stop"] - slot_range["start"] + 1

        return {
            "cluster": cluster_info,
            "statistics": {
                "total_slots": total_slots,
                "shard_count": len(cluster_info.get("shards", [])),
                "version": cluster_info.get("version", 0)
            }
        }

    def health_check(self) -> bool:
        """Check if controller is healthy"""
        try:
            self._request("GET", "/api/v1/namespaces")
            return True
        except Exception:
            return False


class ControllerAPIError(Exception):
    """Exception for controller API errors"""

    def __init__(self, message: str, status_code: int = 0, detail: str = ""):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


class AsyncKVrocksControllerClient:
    """
    Async client for Apache kvrocks-controller HTTP API
    """

    def __init__(
        self,
        controller_url: str,
        timeout: int = 30,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        self.base_url = controller_url.rstrip('/')
        self.timeout = timeout
        self.auth = (username, password) if username and password else None
        self._client = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            auth=self.auth
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make async HTTP request to controller"""
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {}
        except httpx.HTTPStatusError as e:
            logger.error(f"Controller API error: {e.response.status_code} - {e.response.text}")
            raise ControllerAPIError(
                f"API request failed: {e.response.status_code}",
                status_code=e.response.status_code,
                detail=e.response.text
            )
        except Exception as e:
            logger.error(f"Controller request failed: {e}")
            raise ControllerAPIError(f"Request failed: {str(e)}")

    # ==================== Namespace API ====================

    async def list_namespaces(self) -> List[str]:
        result = await self._request("GET", "/api/v1/namespaces")
        # Controller returns {"data": {"namespaces": [...]}}
        data = result.get("data", result)
        return data.get("namespaces", [])

    async def create_namespace(self, namespace: str) -> Dict:
        return await self._request("POST", "/api/v1/namespaces", json={"namespace": namespace})

    async def namespace_exists(self, namespace: str) -> bool:
        try:
            await self._request("GET", f"/api/v1/namespaces/{namespace}")
            return True
        except ControllerAPIError as e:
            if e.status_code == 404:
                return False
            raise

    # ==================== Cluster API ====================

    async def list_clusters(self, namespace: str) -> List[str]:
        result = await self._request("GET", f"/api/v1/namespaces/{namespace}/clusters")
        # Controller returns {"data": {"clusters": [...]}}
        data = result.get("data", result)
        return data.get("clusters", [])

    async def get_cluster(self, namespace: str, cluster: str) -> Dict[str, Any]:
        result = await self._request("GET", f"/api/v1/namespaces/{namespace}/clusters/{cluster}")
        # Controller returns {"data": {"cluster": {...}}}
        data = result.get("data", result)
        return data.get("cluster", data)

    async def create_cluster(
        self,
        namespace: str,
        cluster_name: str,
        nodes: List[str],
        replicas: int = 0,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        data = {"name": cluster_name, "nodes": nodes, "replicas": replicas}
        if password:
            data["password"] = password
        result = await self._request(
            "POST", f"/api/v1/namespaces/{namespace}/clusters", json=data
        )
        # Controller returns {"data": {"cluster": {...}}}
        data_wrapper = result.get("data", result)
        return data_wrapper.get("cluster", data_wrapper)

    async def import_cluster(
        self,
        namespace: str,
        cluster_name: str,
        nodes: List[str],
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        data = {"nodes": nodes}
        if password:
            data["password"] = password
        result = await self._request(
            "POST", f"/api/v1/namespaces/{namespace}/clusters/{cluster_name}/import", json=data
        )
        # Controller returns {"data": {"cluster": {...}}}
        data_wrapper = result.get("data", result)
        return data_wrapper.get("cluster", data_wrapper)

    async def delete_cluster(self, namespace: str, cluster: str) -> bool:
        await self._request("DELETE", f"/api/v1/namespaces/{namespace}/clusters/{cluster}")
        return True

    # ==================== Shard API ====================

    async def list_shards(self, namespace: str, cluster: str) -> List[Dict]:
        result = await self._request(
            "GET", f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards"
        )
        return result.get("shards", [])

    async def get_shard(self, namespace: str, cluster: str, shard_index: int) -> Dict:
        result = await self._request(
            "GET", f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}"
        )
        return result.get("shard", {})

    async def create_shard(
        self,
        namespace: str,
        cluster: str,
        nodes: List[str],
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        data = {"nodes": nodes}
        if password:
            data["password"] = password
        result = await self._request(
            "POST", f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards", json=data
        )
        return result.get("shard", result)

    async def delete_shard(self, namespace: str, cluster: str, shard_index: int) -> bool:
        await self._request(
            "DELETE", f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}"
        )
        return True

    async def failover_shard(
        self,
        namespace: str,
        cluster: str,
        shard_index: int,
        preferred_node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        data = {}
        if preferred_node_id:
            data["preferred_node_id"] = preferred_node_id
        return await self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}/failover",
            json=data
        )

    # ==================== Node API ====================

    async def list_nodes(self, namespace: str, cluster: str, shard_index: int) -> List[Dict]:
        result = await self._request(
            "GET",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}/nodes"
        )
        return result.get("nodes", [])

    async def create_node(
        self,
        namespace: str,
        cluster: str,
        shard_index: int,
        addr: str,
        role: str = "slave",
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        data = {"addr": addr, "role": role}
        if password:
            data["password"] = password
        return await self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}/nodes",
            json=data
        )

    async def delete_node(
        self,
        namespace: str,
        cluster: str,
        shard_index: int,
        node_id: str
    ) -> bool:
        await self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/clusters/{cluster}/shards/{shard_index}/nodes/{node_id}"
        )
        return True

    # ==================== Migration API ====================

    async def migrate_slots(
        self,
        namespace: str,
        cluster: str,
        target_shard: int,
        slot_start: int,
        slot_stop: int,
        slot_only: bool = False
    ) -> Dict[str, Any]:
        # Controller expects slot as string format "start-stop" or "slot"
        if slot_start == slot_stop:
            slot_str = str(slot_start)
        else:
            slot_str = f"{slot_start}-{slot_stop}"

        data = {
            "target": target_shard,
            "slot": slot_str,
            "slot_only": slot_only
        }
        result = await self._request(
            "POST", f"/api/v1/namespaces/{namespace}/clusters/{cluster}/migrate", json=data
        )
        data_wrapper = result.get("data", result)
        return data_wrapper.get("cluster", data_wrapper)

    async def health_check(self) -> bool:
        try:
            await self._request("GET", "/api/v1/namespaces")
            return True
        except Exception:
            return False


def create_controller_client(
    controller_url: str,
    timeout: int = 30,
    username: Optional[str] = None,
    password: Optional[str] = None
) -> KVrocksControllerClient:
    """Factory function to create controller client"""
    return KVrocksControllerClient(controller_url, timeout, username, password)
