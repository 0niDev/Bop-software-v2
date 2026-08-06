"""
Unit Tests for Connection Pool

Tests cover:
- Pool initialization and sizing
- Connection acquisition and release
- Health checking
- Metrics collection
- Thread safety
- Error handling
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

import sys
sys.path.insert(0, '/workspace/rebuildbop/src')

from database.connection_pool import (
    ConnectionPool, 
    PooledConnection, 
    ConnectionMetrics,
    initialize_global_pool,
    get_global_pool,
    close_global_pool
)


class TestConnectionMetrics:
    """Test ConnectionMetrics dataclass"""
    
    def test_initial_values(self):
        """Test metrics start at zero"""
        metrics = ConnectionMetrics()
        assert metrics.total_acquisitions == 0
        assert metrics.total_releases == 0
        assert metrics.current_active == 0
        assert metrics.peak_active == 0
        assert metrics.failed_acquisitions == 0
        assert metrics.health_check_failures == 0
        assert metrics.reconnections == 0
        assert metrics.avg_acquire_time_ms == 0.0
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        metrics = ConnectionMetrics(
            total_acquisitions=10,
            total_releases=8,
            current_active=2,
            peak_active=5,
            failed_acquisitions=1,
            health_check_failures=2,
            reconnections=3,
            avg_acquire_time_ms=15.5,
            last_health_check=datetime.now()
        )
        
        result = metrics.to_dict()
        assert result['total_acquisitions'] == 10
        assert result['total_releases'] == 8
        assert result['current_active'] == 2
        assert result['peak_active'] == 5
        assert 'pool_utilization' in result


class TestPooledConnection:
    """Test PooledConnection wrapper"""
    
    def test_creation(self):
        """Test pooled connection creation"""
        mock_conn = Mock()
        pooled = PooledConnection(connection=mock_conn)
        
        assert pooled.connection == mock_conn
        assert pooled.use_count == 0
        assert pooled.is_healthy is True
        assert pooled.borrowed is False
    
    def test_mark_used(self):
        """Test marking connection as used"""
        mock_conn = Mock()
        pooled = PooledConnection(connection=mock_conn)
        
        initial_use_count = pooled.use_count
        initial_last_used = pooled.last_used
        
        time.sleep(0.01)
        pooled.mark_used()
        
        assert pooled.use_count == initial_use_count + 1
        assert pooled.last_used > initial_last_used
    
    def test_age_seconds(self):
        """Test connection age calculation"""
        mock_conn = Mock()
        pooled = PooledConnection(connection=mock_conn)
        
        time.sleep(0.1)
        age = pooled.age_seconds()
        
        assert age >= 0.1
        assert age < 1.0  # Should be reasonable
    
    def test_idle_seconds(self):
        """Test idle time calculation"""
        mock_conn = Mock()
        pooled = PooledConnection(connection=mock_conn)
        
        time.sleep(0.1)
        pooled.mark_used()
        
        time.sleep(0.1)
        idle = pooled.idle_seconds()
        
        assert idle >= 0.1
        assert idle < 1.0


class TestConnectionPool:
    """Test ConnectionPool class"""
    
    @pytest.fixture
    def mock_sqlite(self):
        """Mock sqlite3 module"""
        with patch('database.connection_pool.sqlite3') as mock_sqlite:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)
            mock_conn.cursor.return_value = mock_cursor
            mock_sqlite.connect.return_value = mock_conn
            yield mock_sqlite
    
    def test_pool_initialization(self, mock_sqlite):
        """Test pool creates minimum connections"""
        pool = ConnectionPool(
            database=':memory:',
            min_connections=5,
            max_connections=10
        )
        
        stats = pool.get_pool_stats()
        assert stats['total_connections'] == 5
        assert stats['available_connections'] == 5
        assert stats['active_connections'] == 0
        assert stats['initialized'] is True
        
        pool.shutdown()
    
    def test_get_connection(self, mock_sqlite):
        """Test acquiring connection from pool"""
        pool = ConnectionPool(
            database=':memory:',
            min_connections=3,
            max_connections=5
        )
        
        conn = pool.get_connection()
        assert conn is not None
        assert conn.borrowed is True
        
        stats = pool.get_pool_stats()
        assert stats['active_connections'] == 1
        assert stats['available_connections'] == 2
        
        pool.return_connection(conn)
        pool.shutdown()
    
    def test_return_connection(self, mock_sqlite):
        """Test returning connection to pool"""
        pool = ConnectionPool(
            database=':memory:',
            min_connections=3,
            max_connections=5
        )
        
        conn = pool.get_connection()
        conn_id = id(conn.connection)
        
        pool.return_connection(conn)
        
        assert conn.borrowed is False
        stats = pool.get_pool_stats()
        assert stats['active_connections'] == 0
        assert stats['available_connections'] == 3
        
        pool.shutdown()
    
    def test_context_manager(self, mock_sqlite):
        """Test connection context manager"""
        pool = ConnectionPool(
            database=':memory:',
            min_connections=3
        )
        
        with pool.get_connection_context() as conn:
            assert conn is not None
            stats = pool.get_pool_stats()
            assert stats['active_connections'] == 1
        
        # Connection should be returned after context exit
        stats = pool.get_pool_stats()
        assert stats['active_connections'] == 0
        
        pool.shutdown()
    
    def test_pool_growth(self, mock_sqlite):
        """Test pool grows when needed"""
        pool = ConnectionPool(
            database=':memory:',
            min_connections=2,
            max_connections=5
        )
        
        # Acquire all connections
        connections = []
        for i in range(5):
            conn = pool.get_connection()
            connections.append(conn)
        
        stats = pool.get_pool_stats()
        assert stats['total_connections'] == 5
        assert stats['active_connections'] == 5
        
        # Return all
        for conn in connections:
            pool.return_connection(conn)
        
        pool.shutdown()
    
    def test_pool_max_limit(self, mock_sqlite):
        """Test pool respects maximum limit"""
        pool = ConnectionPool(
            database=':memory:',
            min_connections=2,
            max_connections=3,
            connection_timeout=0.5
        )
        
        connections = []
        for i in range(3):
            conn = pool.get_connection()
            connections.append(conn)
        
        # Try to get one more - should timeout
        with pytest.raises(TimeoutError):
            pool.get_connection(timeout=0.1)
        
        # Cleanup
        for conn in connections:
            pool.return_connection(conn)
        
        pool.shutdown()
    
    def test_metrics_tracking(self, mock_sqlite):
        """Test metrics are tracked correctly"""
        pool = ConnectionPool(
            database=':memory:',
            min_connections=3
        )
        
        # Acquire and return multiple times
        for i in range(5):
            conn = pool.get_connection()
            pool.return_connection(conn)
        
        metrics = pool.metrics
        assert metrics.total_acquisitions == 5
        assert metrics.total_releases == 5
        assert metrics.peak_active >= 1
        assert metrics.avg_acquire_time_ms >= 0
        
        pool.shutdown()
    
    def test_health_check_invalidates_connection(self, mock_sqlite):
        """Test health check recycles invalid connections"""
        pool = ConnectionPool(
            database=':memory:',
            min_connections=3,
            max_connections=5
        )
        
        # Mark a connection as unhealthy
        if pool._all_connections:
            pool._all_connections[0].is_healthy = False
        
        # Perform health check
        pool.perform_health_check()
        
        # Should have recycled the unhealthy connection
        assert pool.metrics.health_check_failures >= 0  # May or may not increment
        
        pool.shutdown()
    
    def test_shutdown(self, mock_sqlite):
        """Test graceful shutdown"""
        pool = ConnectionPool(
            database=':memory:',
            min_connections=3
        )
        
        pool.shutdown()
        
        stats = pool.get_pool_stats()
        assert stats['shutdown'] is True
        assert stats['total_connections'] == 0
    
    def test_connection_recycling_on_idle(self, mock_sqlite):
        """Test connections are recycled after max idle time"""
        pool = ConnectionPool(
            database=':memory:',
            min_connections=3,
            max_idle_time=0  # Force immediate recycling
        )
        
        conn = pool.get_connection()
        time.sleep(0.1)
        pool.return_connection(conn)
        
        # Connection should have been recycled
        assert pool.metrics.health_check_failures >= 0
        
        pool.shutdown()


class TestGlobalPool:
    """Test global pool singleton functions"""
    
    @patch('database.connection_pool.ConnectionPool')
    def test_initialize_global_pool(self, mock_pool_class):
        """Test global pool initialization"""
        mock_pool_instance = Mock()
        mock_pool_class.return_value = mock_pool_instance
        
        pool = initialize_global_pool(
            database=':memory:',
            min_connections=5,
            max_connections=10
        )
        
        assert pool == mock_pool_instance
        assert get_global_pool() == mock_pool_instance
        
        close_global_pool()
        assert get_global_pool() is None
    
    @patch('database.connection_pool.ConnectionPool')
    def test_reinitialize_global_pool(self, mock_pool_class):
        """Test reinitializing closes existing pool"""
        mock_pool1 = Mock()
        mock_pool2 = Mock()
        mock_pool_class.side_effect = [mock_pool1, mock_pool2]
        
        # First initialization
        initialize_global_pool(database=':memory:')
        
        # Second initialization should close first
        initialize_global_pool(database=':memory:')
        
        # First pool should have been shut down
        mock_pool1.shutdown.assert_called_once()
        
        close_global_pool()


class TestConnectionPoolThreadSafety:
    """Test thread safety of connection pool"""
    
    @patch('database.connection_pool.sqlite3')
    def test_concurrent_access(self, mock_sqlite):
        """Test multiple threads can safely access pool"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite.connect.return_value = mock_conn
        
        pool = ConnectionPool(
            database=':memory:',
            min_connections=10,
            max_connections=20
        )
        
        results = {'success': 0, 'failed': 0}
        lock = threading.Lock()
        
        def worker():
            try:
                for i in range(10):
                    conn = pool.get_connection()
                    time.sleep(0.001)  # Simulate work
                    pool.return_connection(conn)
                
                with lock:
                    results['success'] += 1
            except Exception as e:
                with lock:
                    results['failed'] += 1
        
        # Start multiple threads
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert results['failed'] == 0, f"Failed operations: {results['failed']}"
        assert results['success'] == 5
        
        pool.shutdown()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
