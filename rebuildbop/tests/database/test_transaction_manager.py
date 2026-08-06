"""Tests for TransactionManager."""
import pytest
from unittest.mock import Mock, MagicMock, patch
from src.database.transaction_manager import TransactionManager, BatchTransaction
from src.database.connection_pool import ConnectionPool


class TestTransactionManager:
    """Test TransactionManager functionality."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock database connection."""
        conn = Mock()
        conn.cursor = Mock()
        return conn
    
    @pytest.fixture
    def mock_pool(self, mock_connection):
        """Create mock connection pool."""
        pool = Mock(spec=ConnectionPool)
        pool.borrow_connection = Mock(return_value=mock_connection)
        pool.return_connection = Mock()
        return pool
    
    def test_transaction_begin_commit(self, mock_pool, mock_connection):
        """Test basic transaction begin and commit."""
        tm = TransactionManager(mock_pool, max_retries=3)
        
        with tm.transaction() as txn:
            txn.execute('INSERT INTO accounts VALUES (?, ?)', ('1001', 'Cash'))
        
        # Verify BEGIN was called
        mock_connection.cursor().execute.assert_any_call('BEGIN TRANSACTION')
        # Verify COMMIT was called
        mock_connection.cursor().execute.assert_any_call('COMMIT')
        # Verify connection was returned
        mock_pool.return_connection.assert_called_once()
    
    def test_transaction_rollback_on_error(self, mock_pool, mock_connection):
        """Test transaction rollback on exception."""
        tm = TransactionManager(mock_pool, max_retries=3)
        
        # Make execute raise an exception
        mock_connection.cursor().execute.side_effect = Exception('DB Error')
        
        with pytest.raises(Exception):
            with tm.transaction() as txn:
                txn.execute('INSERT INTO accounts VALUES (?, ?)', ('1001', 'Cash'))
        
        # Verify ROLLBACK was called
        mock_connection.cursor().execute.assert_any_call('ROLLBACK')
    
    def test_savepoint_create_release(self, mock_pool, mock_connection):
        """Test savepoint creation and release."""
        tm = TransactionManager(mock_pool, max_retries=3)
        
        with tm.transaction() as txn:
            sp = txn.savepoint('sp1')
            txn.execute('INSERT INTO accounts VALUES (?, ?)', ('1001', 'Cash'))
            sp.release()
        
        # Verify SAVEPOINT was created
        calls = [call[0][0] for call in mock_connection.cursor().execute.call_args_list]
        assert any('SAVEPOINT sp1' in c for c in calls)
        assert any('RELEASE sp1' in c for c in calls)
    
    def test_savepoint_rollback(self, mock_pool, mock_connection):
        """Test rollback to savepoint."""
        tm = TransactionManager(mock_pool, max_retries=3)
        
        with tm.transaction() as txn:
            sp = txn.savepoint('sp1')
            txn.execute('INSERT INTO accounts VALUES (?, ?)', ('1001', 'Cash'))
            sp.rollback()
        
        # Verify ROLLBACK TO was called
        calls = [call[0][0] for call in mock_connection.cursor().execute.call_args_list]
        assert any('ROLLBACK TO sp1' in c for c in calls)
    
    def test_retry_on_deadlock(self, mock_pool, mock_connection):
        """Test automatic retry on deadlock."""
        tm = TransactionManager(mock_pool, max_retries=3, base_delay_ms=10)
        
        # Simulate deadlock on first two attempts, success on third
        call_count = [0]
        
        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception('SQLITE_BUSY: database is locked')
            return Mock()
        
        mock_connection.cursor().execute.side_effect = execute_side_effect
        
        with tm.transaction() as txn:
            txn.execute('INSERT INTO accounts VALUES (?, ?)', ('1001', 'Cash'))
        
        # Should have retried twice before succeeding
        assert call_count[0] == 3
    
    def test_max_retries_exceeded(self, mock_pool, mock_connection):
        """Test exception after max retries exceeded."""
        tm = TransactionManager(mock_pool, max_retries=2, base_delay_ms=10)
        
        # Always raise deadlock
        mock_connection.cursor().execute.side_effect = Exception('SQLITE_BUSY: database is locked')
        
        with pytest.raises(Exception) as exc_info:
            with tm.transaction() as txn:
                txn.execute('INSERT INTO accounts VALUES (?, ?)', ('1001', 'Cash'))
        
        assert 'max retries exceeded' in str(exc_info.value).lower()


class TestBatchTransaction:
    """Test BatchTransaction functionality."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock database connection."""
        conn = Mock()
        conn.cursor = Mock()
        return conn
    
    @pytest.fixture
    def mock_pool(self, mock_connection):
        """Create mock connection pool."""
        pool = Mock(spec=ConnectionPool)
        pool.borrow_connection = Mock(return_value=mock_connection)
        pool.return_connection = Mock()
        return pool
    
    def test_batch_add_operation(self, mock_pool, mock_connection):
        """Test adding operations to batch."""
        batch = BatchTransaction(mock_pool)
        
        batch.add('INSERT', 'accounts', {'code': '1001', 'name': 'Cash'})
        batch.add('UPDATE', 'accounts', {'name': 'Updated'}, {'code': '1001'})
        
        assert len(batch.operations) == 2
    
    def test_batch_execute_all(self, mock_pool, mock_connection):
        """Test executing all batch operations."""
        batch = BatchTransaction(mock_pool)
        
        batch.add('INSERT', 'accounts', {'code': '1001', 'name': 'Cash'})
        batch.add('INSERT', 'accounts', {'code': '1002', 'name': 'Bank'})
        
        results = batch.execute()
        
        assert len(results) == 2
        assert all(r['success'] for r in results)
    
    def test_batch_rollback_on_failure(self, mock_pool, mock_connection):
        """Test batch rollback when one operation fails."""
        batch = BatchTransaction(mock_pool)
        
        # Make second operation fail
        call_count = [0]
        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception('Constraint violation')
            return Mock()
        
        mock_connection.cursor().execute.side_effect = execute_side_effect
        
        batch.add('INSERT', 'accounts', {'code': '1001', 'name': 'Cash'})
        batch.add('INSERT', 'accounts', {'code': '1002', 'name': 'Bank'})
        
        results = batch.execute()
        
        # First should succeed, second should fail, then rollback
        assert results[0]['success'] is True
        assert results[1]['success'] is False
        assert 'rolled back' in results[1]['error'].lower()
