"""
KVrocks client service
"""
import redis
from redis.cluster import RedisCluster
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class KVrocksClient:
    """KVrocks/Redis client wrapper"""

    def __init__(self, host: str, port: int, password: Optional[str] = None, timeout: int = 5):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._client = None

    @property
    def client(self) -> redis.Redis:
        """Lazy initialization of Redis client"""
        if self._client is None:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                decode_responses=True,
                socket_timeout=self.timeout,
                socket_connect_timeout=self.timeout
            )
        return self._client

    def close(self):
        """Close the connection"""
        if self._client:
            self._client.close()
            self._client = None

    def ping(self) -> bool:
        """Check if the node is alive"""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Ping failed for {self.host}:{self.port}: {e}")
            return False

    def info(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get INFO command result"""
        try:
            if section:
                return self.client.info(section)
            return self.client.info()
        except Exception as e:
            logger.error(f"INFO failed for {self.host}:{self.port}: {e}")
            raise

    def config_get(self, pattern: str = "*") -> Dict[str, str]:
        """Get configuration values"""
        try:
            return self.client.config_get(pattern)
        except Exception as e:
            logger.error(f"CONFIG GET failed for {self.host}:{self.port}: {e}")
            raise

    def config_set(self, name: str, value: str) -> bool:
        """Set a configuration value"""
        try:
            return self.client.config_set(name, value)
        except Exception as e:
            logger.error(f"CONFIG SET failed for {self.host}:{self.port}: {e}")
            raise

    def config_rewrite(self) -> bool:
        """Rewrite the configuration file"""
        try:
            return self.client.config_rewrite()
        except Exception as e:
            logger.error(f"CONFIG REWRITE failed for {self.host}:{self.port}: {e}")
            raise

    def dbsize(self) -> int:
        """Get the number of keys"""
        try:
            return self.client.dbsize()
        except Exception as e:
            logger.error(f"DBSIZE failed for {self.host}:{self.port}: {e}")
            raise

    def execute_command(self, command: str, *args) -> Any:
        """Execute a raw command"""
        try:
            return self.client.execute_command(command, *args)
        except redis.exceptions.ResponseError as e:
            err_msg = str(e)
            # Handle MOVED redirect for cluster mode
            if err_msg.startswith('MOVED '):
                parts = err_msg.split()
                if len(parts) >= 3:
                    target = parts[2]
                    target_host, target_port = target.rsplit(':', 1)
                    redirect_client = redis.Redis(
                        host=target_host,
                        port=int(target_port),
                        password=self.password,
                        decode_responses=True,
                        socket_timeout=self.timeout,
                        socket_connect_timeout=self.timeout
                    )
                    try:
                        return redirect_client.execute_command(command, *args)
                    finally:
                        redirect_client.close()
            logger.error(f"Command '{command}' failed for {self.host}:{self.port}: {e}")
            raise
        except Exception as e:
            logger.error(f"Command '{command}' failed for {self.host}:{self.port}: {e}")
            raise

    def slaveof(self, host: str, port: int) -> bool:
        """Set this node as slave of another node"""
        try:
            return self.client.slaveof(host, port)
        except Exception as e:
            logger.error(f"SLAVEOF failed for {self.host}:{self.port}: {e}")
            raise

    def slaveof_no_one(self) -> bool:
        """Promote this node to master"""
        try:
            return self.client.slaveof()
        except Exception as e:
            logger.error(f"SLAVEOF NO ONE failed for {self.host}:{self.port}: {e}")
            raise

    def bgsave(self) -> bool:
        """Trigger background save"""
        try:
            return self.client.bgsave()
        except Exception as e:
            logger.error(f"BGSAVE failed for {self.host}:{self.port}: {e}")
            raise

    def get_role(self) -> Dict[str, Any]:
        """Get the role of this node (master/slave)"""
        try:
            info = self.client.info('replication')
            return {
                'role': info.get('role', 'unknown'),
                'master_host': info.get('master_host'),
                'master_port': info.get('master_port'),
                'master_link_status': info.get('master_link_status'),
                'connected_slaves': info.get('connected_slaves', 0)
            }
        except Exception as e:
            logger.error(f"Get role failed for {self.host}:{self.port}: {e}")
            raise

    def get_metrics(self) -> Dict[str, float]:
        """Get key metrics for monitoring"""
        try:
            info = self.client.info()
            metrics = {}

            # Memory metrics
            metrics['used_memory'] = float(info.get('used_memory', 0))
            metrics['used_memory_rss'] = float(info.get('used_memory_rss', 0))
            metrics['used_memory_peak'] = float(info.get('used_memory_peak', 0))

            # Client metrics
            metrics['connected_clients'] = float(info.get('connected_clients', 0))
            metrics['blocked_clients'] = float(info.get('blocked_clients', 0))

            # Stats
            metrics['total_connections_received'] = float(info.get('total_connections_received', 0))
            metrics['total_commands_processed'] = float(info.get('total_commands_processed', 0))
            metrics['instantaneous_ops_per_sec'] = float(info.get('instantaneous_ops_per_sec', 0))

            # Keyspace
            metrics['keyspace_hits'] = float(info.get('keyspace_hits', 0))
            metrics['keyspace_misses'] = float(info.get('keyspace_misses', 0))

            # Calculate hit rate
            total_hits = metrics['keyspace_hits'] + metrics['keyspace_misses']
            if total_hits > 0:
                metrics['keyspace_hit_rate'] = metrics['keyspace_hits'] / total_hits * 100
            else:
                metrics['keyspace_hit_rate'] = 0.0

            # CPU
            metrics['used_cpu_sys'] = float(info.get('used_cpu_sys', 0))
            metrics['used_cpu_user'] = float(info.get('used_cpu_user', 0))

            # Replication
            if info.get('role') == 'slave':
                metrics['master_repl_offset'] = float(info.get('master_repl_offset', 0))
                metrics['slave_repl_offset'] = float(info.get('slave_repl_offset', 0))
                # Calculate replication lag
                master_offset = float(info.get('master_repl_offset', 0))
                slave_offset = float(info.get('slave_repl_offset', 0))
                metrics['replication_lag'] = master_offset - slave_offset

            # RocksDB specific metrics (if available)
            rocksdb_info = self.client.info('rocksdb') if 'rocksdb' in info else {}
            if rocksdb_info:
                metrics['rocksdb_estimate_keys'] = float(rocksdb_info.get('estimate_keys', 0))
                metrics['rocksdb_block_cache_usage'] = float(rocksdb_info.get('block_cache_usage', 0))
                metrics['rocksdb_compaction_pending'] = float(rocksdb_info.get('compaction_pending', 0))

            return metrics
        except Exception as e:
            logger.error(f"Get metrics failed for {self.host}:{self.port}: {e}")
            raise

    # ==================== CLUSTER Commands ====================

    def cluster_info(self) -> Dict[str, str]:
        """Get cluster information"""
        try:
            result = self.client.execute_command('CLUSTER', 'INFO')
            info = {}
            for line in result.split('\r\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key] = value
            return info
        except Exception as e:
            logger.error(f"CLUSTER INFO failed for {self.host}:{self.port}: {e}")
            raise

    def cluster_nodes(self) -> List[Dict[str, Any]]:
        """Get cluster nodes information"""
        try:
            result = self.client.execute_command('CLUSTER', 'NODES')
            nodes = []
            for line in result.strip().split('\n'):
                if not line:
                    continue
                parts = line.split()
                node = {
                    'id': parts[0],
                    'address': parts[1].split('@')[0],
                    'flags': parts[2].split(','),
                    'master_id': parts[3] if parts[3] != '-' else None,
                    'ping_sent': int(parts[4]),
                    'pong_recv': int(parts[5]),
                    'config_epoch': int(parts[6]),
                    'link_state': parts[7],
                    'slots': self._parse_slots(parts[8:]) if len(parts) > 8 else []
                }
                nodes.append(node)
            return nodes
        except Exception as e:
            logger.error(f"CLUSTER NODES failed for {self.host}:{self.port}: {e}")
            raise

    def _parse_slots(self, slot_parts: List[str]) -> List[List[int]]:
        """Parse slot ranges from CLUSTER NODES output"""
        slots = []
        for part in slot_parts:
            if '-' in part and not part.startswith('['):
                start, end = part.split('-')
                slots.append([int(start), int(end)])
            elif not part.startswith('['):
                try:
                    slot_num = int(part)
                    slots.append([slot_num, slot_num])
                except ValueError:
                    pass
        return slots

    def cluster_slots(self) -> List[Dict[str, Any]]:
        """Get cluster slot distribution"""
        try:
            result = self.client.execute_command('CLUSTER', 'SLOTS')
            slots_info = []
            for slot_range in result:
                info = {
                    'start': slot_range[0],
                    'end': slot_range[1],
                    'master': {
                        'host': slot_range[2][0],
                        'port': slot_range[2][1],
                        'node_id': slot_range[2][2] if len(slot_range[2]) > 2 else None
                    },
                    'replicas': []
                }
                for replica in slot_range[3:]:
                    info['replicas'].append({
                        'host': replica[0],
                        'port': replica[1],
                        'node_id': replica[2] if len(replica) > 2 else None
                    })
                slots_info.append(info)
            return slots_info
        except Exception as e:
            logger.error(f"CLUSTER SLOTS failed for {self.host}:{self.port}: {e}")
            raise

    def cluster_myid(self) -> str:
        """Get this node's cluster ID"""
        try:
            return self.client.execute_command('CLUSTER', 'MYID')
        except Exception as e:
            logger.error(f"CLUSTER MYID failed for {self.host}:{self.port}: {e}")
            raise

    def cluster_meet(self, host: str, port: int) -> bool:
        """Add a node to the cluster"""
        try:
            self.client.execute_command('CLUSTER', 'MEET', host, port)
            return True
        except Exception as e:
            logger.error(f"CLUSTER MEET failed for {self.host}:{self.port}: {e}")
            raise

    def cluster_forget(self, node_id: str) -> bool:
        """Remove a node from the cluster"""
        try:
            self.client.execute_command('CLUSTER', 'FORGET', node_id)
            return True
        except Exception as e:
            logger.error(f"CLUSTER FORGET failed for {self.host}:{self.port}: {e}")
            raise

    def cluster_replicate(self, master_node_id: str) -> bool:
        """Make this node a replica of the specified master"""
        try:
            self.client.execute_command('CLUSTER', 'REPLICATE', master_node_id)
            return True
        except Exception as e:
            logger.error(f"CLUSTER REPLICATE failed for {self.host}:{self.port}: {e}")
            raise

    def cluster_failover(self, force: bool = False, takeover: bool = False) -> bool:
        """Execute manual failover"""
        try:
            if takeover:
                self.client.execute_command('CLUSTER', 'FAILOVER', 'TAKEOVER')
            elif force:
                self.client.execute_command('CLUSTER', 'FAILOVER', 'FORCE')
            else:
                self.client.execute_command('CLUSTER', 'FAILOVER')
            return True
        except Exception as e:
            logger.error(f"CLUSTER FAILOVER failed for {self.host}:{self.port}: {e}")
            raise

    def cluster_addslots(self, *slots: int) -> bool:
        """Assign slots to this node"""
        try:
            self.client.execute_command('CLUSTER', 'ADDSLOTS', *slots)
            return True
        except Exception as e:
            logger.error(f"CLUSTER ADDSLOTS failed for {self.host}:{self.port}: {e}")
            raise

    def cluster_delslots(self, *slots: int) -> bool:
        """Remove slots from this node"""
        try:
            self.client.execute_command('CLUSTER', 'DELSLOTS', *slots)
            return True
        except Exception as e:
            logger.error(f"CLUSTER DELSLOTS failed for {self.host}:{self.port}: {e}")
            raise

    def cluster_setslot_importing(self, slot: int, source_node_id: str) -> bool:
        """Set slot as importing from source node"""
        try:
            self.client.execute_command('CLUSTER', 'SETSLOT', slot, 'IMPORTING', source_node_id)
            return True
        except Exception as e:
            logger.error(f"CLUSTER SETSLOT IMPORTING failed: {e}")
            raise

    def cluster_setslot_migrating(self, slot: int, target_node_id: str) -> bool:
        """Set slot as migrating to target node"""
        try:
            self.client.execute_command('CLUSTER', 'SETSLOT', slot, 'MIGRATING', target_node_id)
            return True
        except Exception as e:
            logger.error(f"CLUSTER SETSLOT MIGRATING failed: {e}")
            raise

    def cluster_setslot_node(self, slot: int, node_id: str) -> bool:
        """Assign slot to specified node"""
        try:
            self.client.execute_command('CLUSTER', 'SETSLOT', slot, 'NODE', node_id)
            return True
        except Exception as e:
            logger.error(f"CLUSTER SETSLOT NODE failed: {e}")
            raise

    def cluster_setslot_stable(self, slot: int) -> bool:
        """Clear importing/migrating state for slot"""
        try:
            self.client.execute_command('CLUSTER', 'SETSLOT', slot, 'STABLE')
            return True
        except Exception as e:
            logger.error(f"CLUSTER SETSLOT STABLE failed: {e}")
            raise

    def cluster_getkeysinslot(self, slot: int, count: int) -> List[str]:
        """Get keys in the specified slot"""
        try:
            return self.client.execute_command('CLUSTER', 'GETKEYSINSLOT', slot, count)
        except Exception as e:
            logger.error(f"CLUSTER GETKEYSINSLOT failed: {e}")
            raise

    def cluster_countkeysinslot(self, slot: int) -> int:
        """Count keys in the specified slot"""
        try:
            return self.client.execute_command('CLUSTER', 'COUNTKEYSINSLOT', slot)
        except Exception as e:
            logger.error(f"CLUSTER COUNTKEYSINSLOT failed: {e}")
            raise

    def migrate(self, host: str, port: int, key: str,
                db: int = 0, timeout: int = 5000,
                copy: bool = False, replace: bool = True,
                auth: Optional[str] = None) -> bool:
        """Migrate a single key to target node"""
        try:
            args = ['MIGRATE', host, port, key, db, timeout]
            if copy:
                args.append('COPY')
            if replace:
                args.append('REPLACE')
            if auth:
                args.extend(['AUTH', auth])
            self.client.execute_command(*args)
            return True
        except Exception as e:
            logger.error(f"MIGRATE failed for key {key}: {e}")
            raise

    def migrate_keys(self, host: str, port: int, keys: List[str],
                     db: int = 0, timeout: int = 5000,
                     copy: bool = False, replace: bool = True,
                     auth: Optional[str] = None) -> bool:
        """Migrate multiple keys to target node"""
        try:
            args = ['MIGRATE', host, port, '', db, timeout]
            if copy:
                args.append('COPY')
            if replace:
                args.append('REPLACE')
            if auth:
                args.extend(['AUTH', auth])
            args.append('KEYS')
            args.extend(keys)
            self.client.execute_command(*args)
            return True
        except Exception as e:
            logger.error(f"MIGRATE KEYS failed: {e}")
            raise


def create_kvrocks_client(host: str, port: int, password: Optional[str] = None) -> KVrocksClient:
    """Factory function to create KVrocks client"""
    return KVrocksClient(host, port, password)
