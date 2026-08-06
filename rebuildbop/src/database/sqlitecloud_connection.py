"""
SQLite Cloud connection manager with connection pooling.

This module provides a robust SQLite Cloud connection implementation with:
- Connection pooling (min 10, max 50 connections)
- Automatic retry logic with exponential backoff
- Transaction management with savepoints
- Deadlock detection and recovery
"""
from __future__ import annotations

import os
import time
import sqlitecloud
import logging
from contextlib import contextmanager
from typing import Any, Iterator, Sequence, Optional
from dataclasses import dataclass, field
from collections import deque
from threading import Lock

from src.config.database_config import get_sqlite_cloud_url, SQLITE_CLOUD_API_KEY

logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolConfig:
    """Configuration for connection pool."""
    min_connections: int = 10
    max_connections: int = 50
    connection_timeout: float = 30.0
    retry_attempts: int = 3
    retry_delays: tuple = (0.1, 0.5, 2.0)  # Exponential backoff: 100ms, 500ms, 2s
    

@dataclass
class PooledConnection:
    """Wrapper for pooled SQLite Cloud connection."""
    connection: Any
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    in_use: bool = False


class SQLiteCloudConnection:
    """
    SQLite Cloud connection with pooling and retry logic.
    
    Features:
    - Connection pooling to reduce connection overhead
    - Automatic retry with exponential backoff
    - Transaction management with rollback support
    - Thread-safe connection management
    """
    
    # Class-level connection pool
    _connection_pool: deque[PooledConnection] = deque()
    _pool_lock = Lock()
    _pool_initialized = False
    _config: Optional[ConnectionPoolConfig] = None
    
    def __init__(self, config: Optional[ConnectionPoolConfig] = None):
        """
        Initialize SQLite Cloud connection.
        
        Args:
            config: Optional pool configuration. Uses defaults if not provided.
        """
        self._config = config or ConnectionPoolConfig()
        self._conn: Optional[Any] = None
        self._in_transaction = False
        
        # Get connection from pool
        self._conn = self._get_from_pool()
        if self._conn is None:
            self._connect()
    
    @classmethod
    def initialize_pool(cls, config: Optional[ConnectionPoolConfig] = None) -> None:
        """
        Initialize connection pool with minimum connections.
        
        Args:
            config: Pool configuration. Creates default if not provided.
        """
        if cls._pool_initialized:
            return
        
        config = config or ConnectionPoolConfig()
        logger.info(f"Initializing SQLite Cloud connection pool (min={config.min_connections}, max={config.max_connections})")
        
        with cls._pool_lock:
            for i in range(config.min_connections):
                try:
                    conn = cls._create_connection()
                    pooled_conn = PooledConnection(connection=conn)
                    cls._connection_pool.append(pooled_conn)
                    logger.debug(f"Created pooled connection {i+1}/{config.min_connections}")
                except Exception as e:
                    logger.warning(f"Could not create pooled connection {i+1}: {e}")
            
            cls._config = config
            cls._pool_initialized = True
            logger.info(f"Initialized {len(cls._connection_pool)} pooled connections")
    
    @classmethod
    def _create_connection(cls) -> Any:
        """
        Create a new SQLite Cloud connection.
        
        Returns:
            SQLite Cloud connection object
            
        Raises:
            DatabaseError: If connection fails
        """
        connection_string = get_sqlite_cloud_url()
        
        if not connection_string:
            raise DatabaseError("SQLITE_CLOUD_URL not configured")
        
        conn = sqlitecloud.connect(connection_string)
        
        # Optimize connection settings
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        conn.execute("PRAGMA temp_store = MEMORY")
        
        return conn
    
    @classmethod
    def _get_from_pool(cls) -> Optional[Any]:
        """
        Get a connection from the pool if available.
        
        Returns:
            Connection object or None if pool is empty
        """
        with cls._pool_lock:
            while cls._connection_pool:
                pooled_conn = cls._connection_pool.popleft()
                
                # Check if connection is still valid
                if not pooled_conn.in_use:
                    pooled_conn.in_use = True
                    pooled_conn.last_used = time.time()
                    return pooled_conn.connection
            
            return None
    
    @classmethod
    def _return_to_pool(cls, conn: Any) -> None:
        """
        Return a connection to the pool.
        
        Args:
            conn: Connection object to return
        """
        with cls._pool_lock:
            # Find existing pooled connection or create new one
            for pooled_conn in cls._connection_pool:
                if pooled_conn.connection == conn:
                    pooled_conn.in_use = False
                    pooled_conn.last_used = time.time()
                    return
            
            # Add new pooled connection if under max
            if len(cls._connection_pool) < cls._config.max_connections if cls._config else 50:
                pooled_conn = PooledConnection(connection=conn)
                cls._connection_pool.append(pooled_conn)
    
    def _connect(self) -> None:
        """
        Establish SQLite Cloud connection with retry logic.
        
        Raises:
            DatabaseError: If all retry attempts fail
        """
        config = self._config or ConnectionPoolConfig()
        last_error = None
        
        for attempt in range(config.retry_attempts):
            try:
                self._conn = self._create_connection()
                logger.info("Connected to SQLite Cloud database")
                return
            except Exception as e:
                last_error = e
                if attempt < config.retry_attempts - 1:
                    delay = config.retry_delays[attempt] if attempt < len(config.retry_delays) else 2.0
                    logger.warning(f"Connection attempt {attempt+1} failed, retrying in {delay}s... ({e})")
                    time.sleep(delay)
                else:
                    logger.error(f"All {config.retry_attempts} connection attempts failed")
        
        raise DatabaseError(f"Could not connect to SQLite Cloud: {last_error}")
    
    def _ensure_connection(self) -> None:
        """Ensure connection is active, reconnect if needed."""
        if self._conn is None:
            self._connect()
    
    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        """
        Execute SQL statement with retry logic.
        
        Args:
            sql: SQL query string
            params: Query parameters
            
        Returns:
            Cursor object
            
        Raises:
            DatabaseError: If execution fails after retries
        """
        self._ensure_connection()
        config = self._config or ConnectionPoolConfig()
        
        for attempt in range(config.retry_attempts):
            try:
                return self._conn.execute(sql, params)
            except Exception as e:
                error_msg = str(e).lower()
                
                # Retry on write conflicts or connection issues
                if any(keyword in error_msg for keyword in ["write", "locked", "busy"]) and attempt < config.retry_attempts - 1:
                    delay = config.retry_delays[attempt] if attempt < len(config.retry_delays) else 2.0
                    logger.warning(f"Write error, retrying in {delay}s... (attempt {attempt+1})")
                    time.sleep(delay)
                    self._ensure_connection()
                    continue
                
                logger.error(f"SQL execute failed: {e} | sql={sql}")
                raise DatabaseError(str(e))
        
        raise DatabaseError("Failed to execute SQL after retries")
    
    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict]:
        """
        Execute SQL and fetch one result.
        
        Args:
            sql: SQL query string
            params: Query parameters
            
        Returns:
            Dictionary with column names as keys, or None if no results
        """
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        if isinstance(row, tuple):
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        
        return row
    
    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        """
        Execute SQL and fetch all results.
        
        Args:
            sql: SQL query string
            params: Query parameters
            
        Returns:
            List of dictionaries with column names as keys
        """
        cursor = self.execute(sql, params)
        rows = cursor.fetchall()
        
        if not rows:
            return []
        
        if isinstance(rows[0], tuple):
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        
        return rows
    
    def executemany(self, sql: str, seq_of_params: Sequence[Sequence[Any]]) -> Any:
        """
        Execute SQL for multiple parameter sets (batch operation).
        
        Args:
            sql: SQL query string
            seq_of_params: Sequence of parameter tuples
            
        Returns:
            Cursor object
        """
        self._ensure_connection()
        cursor = self._conn.cursor()
        cursor.executemany(sql, seq_of_params)
        return cursor
    
    def last_insert_id(self) -> int:
        """Get the last inserted row ID."""
        self._ensure_connection()
        cursor = self._conn.execute("SELECT last_insert_rowid()")
        return cursor.fetchone()[0]
    
    @contextmanager
    def transaction(self) -> Iterator['SQLiteCloudConnection']:
        """
        Context manager for database transactions.
        
        Usage:
            with db.transaction() as tx:
                tx.execute("INSERT INTO ...")
                tx.execute("UPDATE ...")
        
        Automatically commits on success, rolls back on exception.
        """
        self._ensure_connection()
        self._in_transaction = True
        
        try:
            self._conn.execute("BEGIN")
            yield self
            self._conn.execute("COMMIT")
            self._in_transaction = False
        except Exception as e:
            self._conn.execute("ROLLBACK")
            self._in_transaction = False
            logger.error(f"Transaction rolled back: {e}")
            raise
    
    @contextmanager
    def savepoint(self, name: str) -> Iterator['SQLiteCloudConnection']:
        """
        Context manager for savepoints within a transaction.
        
        Args:
            name: Savepoint name
            
        Usage:
            with db.transaction() as tx:
                tx.execute("INSERT ...")
                with tx.savepoint('sp1'):
                    tx.execute("INSERT ...")  # Can be rolled back independently
        """
        self._ensure_connection()
        
        try:
            self._conn.execute(f"SAVEPOINT {name}")
            yield self
            self._conn.execute(f"RELEASE SAVEPOINT {name}")
        except Exception as e:
            self._conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
            logger.error(f"Savepoint {name} rolled back: {e}")
            raise
    
    def close(self) -> None:
        """Return connection to pool instead of closing it."""
        if self._conn:
            self._return_to_pool(self._conn)
            self._conn = None
            self._in_transaction = False
    
    @classmethod
    def close_all(cls) -> None:
        """Close all pooled connections (call on application shutdown)."""
        with cls._pool_lock:
            for pooled_conn in cls._connection_pool:
                try:
                    pooled_conn.connection.close()
                except Exception:
                    pass
            cls._connection_pool.clear()
            cls._pool_initialized = False
            logger.info("Closed all pooled SQLite Cloud connections")


class DatabaseError(Exception):
    """Custom exception for database errors."""
    pass
