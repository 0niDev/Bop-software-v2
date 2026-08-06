"""
Connection Pool Manager for SQLite Cloud

Implements intelligent connection pooling with:
- Dynamic pool sizing (min 10, max 50 connections)
- Health checking and auto-reconnection
- Connection metrics and monitoring
- Thread-safe connection borrowing/returning

Performance Targets:
- Connection acquisition: < 10ms
- Health check: < 50ms
- Auto-reconnect: < 500ms
"""

import sqlite3
import threading
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import contextmanager
import queue

logger = logging.getLogger(__name__)


@dataclass
class ConnectionMetrics:
    """Track connection pool metrics for monitoring"""
    total_acquisitions: int = 0
    total_releases: int = 0
    current_active: int = 0
    peak_active: int = 0
    failed_acquisitions: int = 0
    health_check_failures: int = 0
    reconnections: int = 0
    avg_acquire_time_ms: float = 0.0
    last_health_check: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for reporting"""
        return {
            'total_acquisitions': self.total_acquisitions,
            'total_releases': self.total_releases,
            'current_active': self.current_active,
            'peak_active': self.peak_active,
            'failed_acquisitions': self.failed_acquisitions,
            'health_check_failures': self.health_check_failures,
            'reconnections': self.reconnections,
            'avg_acquire_time_ms': round(self.avg_acquire_time_ms, 2),
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'pool_utilization': f"{(self.current_active / max(self.current_active, 1)) * 100:.1f}%"
        }


@dataclass
class PooledConnection:
    """Wrapper for database connections with metadata"""
    connection: sqlite3.Connection
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    use_count: int = 0
    is_healthy: bool = True
    borrowed: bool = False
    
    def mark_used(self):
        """Mark connection as recently used"""
        self.last_used = datetime.now()
        self.use_count += 1
    
    def age_seconds(self) -> float:
        """Get connection age in seconds"""
        return (datetime.now() - self.created_at).total_seconds()
    
    def idle_seconds(self) -> float:
        """Get idle time in seconds"""
        return (datetime.now() - self.last_used).total_seconds()


class ConnectionPool:
    """
    Thread-safe connection pool for SQLite Cloud
    
    Features:
    - Dynamic pool sizing based on demand
    - Automatic health checking
    - Connection recycling
    - Metrics collection
    - Graceful degradation on failures
    
    Usage:
        pool = ConnectionPool(
            database='cloud://server.db',
            min_connections=10,
            max_connections=50,
            health_check_interval=30
        )
        
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM accounts')
    """
    
    def __init__(
        self,
        database: str,
        min_connections: int = 10,
        max_connections: int = 50,
        health_check_interval: int = 30,
        connection_timeout: float = 5.0,
        max_idle_time: int = 600,
        max_lifetime: int = 3600,
        retry_attempts: int = 3,
        retry_delay: float = 0.1
    ):
        """
        Initialize connection pool
        
        Args:
            database: SQLite Cloud connection string or file path
            min_connections: Minimum connections to maintain
            max_connections: Maximum connections allowed
            health_check_interval: Seconds between health checks
            connection_timeout: Timeout for acquiring connection
            max_idle_time: Max idle time before connection recycling
            max_lifetime: Max connection lifetime before recycling
            retry_attempts: Number of retry attempts on failure
            retry_delay: Base delay between retries (exponential backoff)
        """
        self.database = database
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.health_check_interval = health_check_interval
        self.connection_timeout = connection_timeout
        self.max_idle_time = max_idle_time
        self.max_lifetime = max_lifetime
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        
        # Connection storage
        self._available: queue.Queue[PooledConnection] = queue.Queue()
        self._in_use: Dict[int, PooledConnection] = {}
        self._all_connections: List[PooledConnection] = []
        
        # Thread safety
        self._lock = threading.RLock()
        self._health_check_lock = threading.Lock()
        
        # Metrics
        self.metrics = ConnectionMetrics()
        self._acquire_times: List[float] = []
        
        # State
        self._initialized = False
        self._shutdown = False
        self._last_health_check = datetime.now() - timedelta(seconds=health_check_interval)
        
        # Initialize pool
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Create initial connections up to min_connections"""
        logger.info(f"Initializing connection pool: min={self.min_connections}, max={self.max_connections}")
        
        try:
            for i in range(self.min_connections):
                conn = self._create_connection()
                pooled = PooledConnection(connection=conn)
                self._available.put(pooled)
                self._all_connections.append(pooled)
            
            self._initialized = True
            logger.info(f"Connection pool initialized with {self.min_connections} connections")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    def _create_connection(self) -> sqlite3.Connection:
        """
        Create a new database connection with optimized settings
        
        Returns:
            Configured sqlite3.Connection
        """
        # Detect if this is a cloud connection or local
        if self.database.startswith('cloud://'):
            # SQLite Cloud connection
            import sqlitecloud
            conn = sqlitecloud.connect(self.database)
        else:
            # Local SQLite with WAL mode for better concurrency
            conn = sqlite3.connect(self.database, timeout=self.connection_timeout)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=-64000')  # 64MB cache
            conn.execute('PRAGMA temp_store=MEMORY')
            conn.row_factory = sqlite3.Row
        
        # Common settings
        conn.execute('PRAGMA foreign_keys=ON')
        
        return conn
    
    def _test_connection(self, conn: sqlite3.Connection) -> bool:
        """
        Test if connection is healthy
        
        Args:
            conn: Connection to test
            
        Returns:
            True if connection is healthy
        """
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            return result is not None and result[0] == 1
        except Exception:
            return False
    
    def _is_connection_valid(self, pooled: PooledConnection) -> bool:
        """
        Check if pooled connection is still valid
        
        Args:
            pooled: PooledConnection to check
            
        Returns:
            True if connection should be kept
        """
        # Check if explicitly marked unhealthy
        if not pooled.is_healthy:
            return False
        
        # Check idle time
        if pooled.idle_seconds() > self.max_idle_time:
            logger.debug(f"Connection idle too long: {pooled.idle_seconds():.1f}s")
            return False
        
        # Check lifetime
        if pooled.age_seconds() > self.max_lifetime:
            logger.debug(f"Connection expired: {pooled.age_seconds():.1f}s")
            return False
        
        # Test actual connectivity
        if not self._test_connection(pooled.connection):
            return False
        
        return True
    
    def _recycle_connection(self, pooled: PooledConnection):
        """
        Close and remove unhealthy connection
        
        Args:
            pooled: PooledConnection to recycle
        """
        try:
            pooled.connection.close()
        except Exception:
            pass  # Ignore errors on close
        
        if pooled in self._all_connections:
            self._all_connections.remove(pooled)
        
        self.metrics.reconnections += 1
        logger.debug("Connection recycled")
    
    def _create_new_connection(self) -> PooledConnection:
        """
        Create a new pooled connection with retry logic
        
        Returns:
            New PooledConnection
            
        Raises:
            ConnectionError: If unable to create connection after retries
        """
        last_error = None
        
        for attempt in range(self.retry_attempts):
            try:
                conn = self._create_connection()
                pooled = PooledConnection(connection=conn)
                
                # Verify connection works
                if self._test_connection(conn):
                    self._all_connections.append(pooled)
                    logger.debug(f"Created new connection (attempt {attempt + 1})")
                    return pooled
                else:
                    conn.close()
                    last_error = Exception("Connection test failed")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Connection creation failed (attempt {attempt + 1}): {e}")
                
                if attempt < self.retry_attempts - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)
        
        self.metrics.failed_acquisitions += 1
        raise ConnectionError(f"Failed to create connection after {self.retry_attempts} attempts") from last_error
    
    def get_connection(self, timeout: Optional[float] = None) -> PooledConnection:
        """
        Acquire a connection from the pool
        
        Args:
            timeout: Override default timeout
            
        Returns:
            PooledConnection
            
        Raises:
            TimeoutError: If unable to acquire connection within timeout
            ConnectionError: If pool is exhausted and cannot grow
        """
        if self._shutdown:
            raise ConnectionError("Connection pool is shut down")
        
        start_time = time.time()
        effective_timeout = timeout or self.connection_timeout
        
        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > effective_timeout:
                self.metrics.failed_acquisitions += 1
                raise TimeoutError(
                    f"Timeout acquiring connection after {elapsed:.2f}s. "
                    f"Active: {len(self._in_use)}, Available: {self._available.qsize()}"
                )
            
            # Try to get available connection
            try:
                pooled = self._available.get_nowait()
                
                # Validate connection
                if self._is_connection_valid(pooled):
                    pooled.mark_used()
                    pooled.borrowed = True
                    
                    with self._lock:
                        self._in_use[id(pooled.connection)] = pooled
                    
                    # Update metrics
                    acquire_time = (time.time() - start_time) * 1000
                    self._acquire_times.append(acquire_time)
                    if len(self._acquire_times) > 100:
                        self._acquire_times.pop(0)
                    self.metrics.avg_acquire_time_ms = sum(self._acquire_times) / len(self._acquire_times)
                    
                    self.metrics.total_acquisitions += 1
                    self.metrics.current_active = len(self._in_use)
                    self.metrics.peak_active = max(self.metrics.peak_active, self.metrics.current_active)
                    
                    logger.debug(f"Connection acquired in {acquire_time:.2f}ms")
                    return pooled
                else:
                    # Connection invalid, recycle and try again
                    self._recycle_connection(pooled)
                    self.metrics.health_check_failures += 1
                    
            except queue.Empty:
                # No available connections, try to create new one
                with self._lock:
                    if len(self._all_connections) < self.max_connections:
                        try:
                            pooled = self._create_new_connection()
                            pooled.mark_used()
                            pooled.borrowed = True
                            self._in_use[id(pooled.connection)] = pooled
                            
                            # Update metrics
                            acquire_time = (time.time() - start_time) * 1000
                            self.metrics.total_acquisitions += 1
                            self.metrics.current_active = len(self._in_use)
                            self.metrics.peak_active = max(self.metrics.peak_active, self.metrics.current_active)
                            
                            return pooled
                        except Exception as e:
                            logger.warning(f"Cannot create new connection: {e}")
                
                # Pool exhausted, wait for available connection
                time.sleep(0.01)  # Small sleep to prevent busy waiting
    
    def return_connection(self, pooled: PooledConnection):
        """
        Return a connection to the pool
        
        Args:
            pooled: PooledConnection to return
        """
        if not pooled.borrowed:
            logger.warning("Attempting to return connection that wasn't borrowed")
            return
        
        pooled.borrowed = False
        
        with self._lock:
            if id(pooled.connection) in self._in_use:
                del self._in_use[id(pooled.connection)]
        
        # Check if connection should be recycled
        if not self._is_connection_valid(pooled):
            self._recycle_connection(pooled)
            self.metrics.health_check_failures += 1
            
            # Try to create replacement if below minimum
            with self._lock:
                if len(self._all_connections) < self.min_connections:
                    try:
                        new_pooled = self._create_new_connection()
                        self._available.put(new_pooled)
                    except Exception as e:
                        logger.warning(f"Failed to create replacement connection: {e}")
        else:
            # Return to pool
            self._available.put(pooled)
        
        self.metrics.total_releases += 1
        self.metrics.current_active = len(self._in_use)
        
        logger.debug("Connection returned to pool")
    
    @contextmanager
    def get_connection_context(self):
        """
        Context manager for acquiring/releasing connections
        
        Usage:
            with pool.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM accounts')
        
        Yields:
            sqlite3.Connection
        """
        pooled = None
        try:
            pooled = self.get_connection()
            yield pooled.connection
        finally:
            if pooled:
                self.return_connection(pooled)
    
    def perform_health_check(self):
        """
        Perform health check on all connections
        
        Should be called periodically by a background thread
        """
        if not self._health_check_lock.acquire(blocking=False):
            return  # Another thread is already doing health check
        
        try:
            now = datetime.now()
            if (now - self._last_health_check).total_seconds() < self.health_check_interval:
                return
            
            self._last_health_check = now
            self.metrics.last_health_check = now
            
            healthy_count = 0
            unhealthy_count = 0
            
            # Check all connections
            all_to_check = list(self._all_connections)
            for pooled in all_to_check:
                if not self._is_connection_valid(pooled):
                    self._recycle_connection(pooled)
                    unhealthy_count += 1
                else:
                    healthy_count += 1
            
            # Ensure minimum connections
            with self._lock:
                while len(self._all_connections) < self.min_connections:
                    try:
                        new_pooled = self._create_new_connection()
                        self._all_connections.append(new_pooled)
                        self._available.put(new_pooled)
                    except Exception as e:
                        logger.warning(f"Failed to create connection during health check: {e}")
                        break
            
            if unhealthy_count > 0:
                logger.info(f"Health check: {healthy_count} healthy, {unhealthy_count} recycled")
                
        finally:
            self._health_check_lock.release()
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get current pool statistics
        
        Returns:
            Dictionary with pool statistics
        """
        return {
            'database': self.database,
            'min_connections': self.min_connections,
            'max_connections': self.max_connections,
            'total_connections': len(self._all_connections),
            'available_connections': self._available.qsize(),
            'active_connections': len(self._in_use),
            'metrics': self.metrics.to_dict(),
            'initialized': self._initialized,
            'shutdown': self._shutdown
        }
    
    def shutdown(self, wait_timeout: float = 10.0):
        """
        Gracefully shutdown the pool
        
        Args:
            wait_timeout: Time to wait for active connections
        """
        logger.info("Shutting down connection pool")
        self._shutdown = True
        
        # Wait for active connections to be returned
        start_time = time.time()
        while self._in_use and (time.time() - start_time) < wait_timeout:
            time.sleep(0.1)
        
        if self._in_use:
            logger.warning(f"Closing pool with {len(self._in_use)} active connections")
        
        # Close all connections
        closed_count = 0
        for pooled in self._all_connections:
            try:
                pooled.connection.close()
                closed_count += 1
            except Exception:
                pass
        
        # Clear collections
        self._available = queue.Queue()
        self._in_use.clear()
        self._all_connections.clear()
        
        logger.info(f"Connection pool shutdown complete. Closed {closed_count} connections.")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.shutdown()


# Singleton instance for global access
_pool_instance: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def get_global_pool() -> Optional[ConnectionPool]:
    """Get the global connection pool instance"""
    return _pool_instance


def initialize_global_pool(
    database: str,
    min_connections: int = 10,
    max_connections: int = 50,
    **kwargs
) -> ConnectionPool:
    """
    Initialize the global connection pool
    
    Args:
        database: Database connection string
        min_connections: Minimum pool size
        max_connections: Maximum pool size
        **kwargs: Additional arguments for ConnectionPool
        
    Returns:
        Initialized ConnectionPool instance
    """
    global _pool_instance
    
    with _pool_lock:
        if _pool_instance is not None:
            logger.warning("Global pool already initialized, closing existing pool")
            _pool_instance.shutdown()
        
        _pool_instance = ConnectionPool(
            database=database,
            min_connections=min_connections,
            max_connections=max_connections,
            **kwargs
        )
        
        logger.info("Global connection pool initialized")
        return _pool_instance


def close_global_pool():
    """Close the global connection pool"""
    global _pool_instance
    
    with _pool_lock:
        if _pool_instance:
            _pool_instance.shutdown()
            _pool_instance = None
            logger.info("Global connection pool closed")
