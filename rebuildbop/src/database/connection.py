"""
Database connection manager for BOP Pharmaceutical ERP.

This module provides a simple interface to get database connections
from the connection pool.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.database.sqlitecloud_connection import (
    SQLiteCloudConnection,
    ConnectionPoolConfig,
    DatabaseError,
)

logger = logging.getLogger(__name__)

# Global database instance (singleton pattern)
_db_instance: Optional[SQLiteCloudConnection] = None


def get_db() -> SQLiteCloudConnection:
    """
    Get a database connection from the pool.
    
    Returns:
        SQLiteCloudConnection instance
        
    Example:
        db = get_db()
        result = db.fetch_one("SELECT * FROM users WHERE id = ?", (1,))
    """
    global _db_instance
    
    if _db_instance is None:
        # Initialize connection pool on first use
        config = ConnectionPoolConfig(
            min_connections=10,
            max_connections=50,
            retry_attempts=3,
        )
        SQLiteCloudConnection.initialize_pool(config)
        _db_instance = SQLiteCloudConnection(config)
        logger.info("Database connection pool initialized")
    
    return _db_instance


def close_db() -> None:
    """
    Close all database connections.
    
    Call this on application shutdown to properly release resources.
    """
    global _db_instance
    
    if _db_instance is not None:
        _db_instance.close()
        _db_instance = None
    
    SQLiteCloudConnection.close_all()
    logger.info("Database connections closed")


def test_connection() -> bool:
    """
    Test database connection.
    
    Returns:
        True if connection is successful, False otherwise
        
    Example:
        if test_connection():
            print("Database is connected")
        else:
            print("Database connection failed")
    """
    try:
        db = get_db()
        # Simple query to test connection
        result = db.fetch_one("SELECT 1 as test")
        return result is not None and result.get('test') == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


__all__ = [
    'get_db',
    'close_db',
    'test_connection',
    'SQLiteCloudConnection',
    'ConnectionPoolConfig',
    'DatabaseError',
]
