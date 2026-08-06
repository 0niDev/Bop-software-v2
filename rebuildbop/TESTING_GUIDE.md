# BOP ERP Testing Guide
======================

## Quick Start: How to Test Each Phase

### Prerequisites Setup

```bash
cd /workspace/rebuildbop

# Install dependencies
pip install pytest pytest-cov pytest-asyncio sqlitecloud

# Set environment variables (optional - uses defaults if not set)
export SQLITE_CLOUD_HOST=localhost
export SQLITE_CLOUD_PORT=8443
export SQLITE_CLOUD_USERNAME=test_user
export SQLITE_CLOUD_PASSWORD=test_pass
export SQLITE_CLOUD_DATABASE=bop_test
```

---

## PHASE 2: Database Layer Testing

### 1. Test Connection Pool

```bash
# Run all connection pool tests
pytest tests/database/test_connection_pool.py -v

# Run specific test
pytest tests/database/test_connection_pool.py::test_connection_pool_creation -v

# Run with coverage
pytest tests/database/test_connection_pool.py --cov=src/database --cov-report=html
```

**What it tests:**
- ✅ Pool creation with min/max connections
- ✅ Connection borrowing and returning
- ✅ Thread safety
- ✅ Health checking
- ✅ Metrics collection
- ✅ Error handling

### 2. Test Query Builder

```bash
# Create test file first (see below)
pytest tests/database/test_query_builder.py -v
```

### 3. Test Transaction Manager

```bash
# Create test file first (see below)
pytest tests/database/test_transaction_manager.py -v
```

### 4. Test Migrations

```bash
# Run migration tests
pytest tests/database/test_migrations.py -v

# Test migration rollback
pytest tests/database/test_migrations.py::test_migration_rollback -v
```

### 5. Run All Database Tests

```bash
# All database layer tests
pytest tests/database/ -v

# With coverage report
pytest tests/database/ --cov=src/database --cov-report=term-missing

# Generate HTML coverage report
pytest tests/database/ --cov=src/database --cov-report=html
# Open: rebuildbop/htmlcov/index.html
```

---

## Test Files You Need to Create

### File: `tests/database/test_query_builder.py`

```python
"""Tests for QueryBuilder and related components."""
import pytest
from src.database.query_builder import QueryBuilder, QueryCache, BulkOperations


class TestQueryBuilder:
    """Test QueryBuilder functionality."""
    
    def test_select_basic(self):
        """Test basic SELECT query."""
        qb = QueryBuilder().select('*').from_('accounts')
        sql, params = qb.build()
        
        assert 'SELECT * FROM accounts' in sql
        assert params == []
    
    def test_select_with_where(self):
        """Test SELECT with WHERE clause."""
        qb = (QueryBuilder()
              .select('code', 'name')
              .from_('accounts')
              .where('account_type', '=', 'ASSET')
              .where('is_active', '=', True))
        sql, params = qb.build()
        
        assert 'SELECT code, name FROM accounts' in sql
        assert 'WHERE account_type = ? AND is_active = ?' in sql
        assert params == ['ASSET', True]
    
    def test_insert_query(self):
        """Test INSERT query."""
        qb = QueryBuilder().insert('accounts', {
            'code': '1001',
            'name': 'Cash',
            'account_type': 'ASSET'
        })
        sql, params = qb.build()
        
        assert 'INSERT INTO accounts' in sql
        assert len(params) == 3
    
    def test_update_query(self):
        """Test UPDATE query."""
        qb = (QueryBuilder()
              .update('accounts')
              .set({'name': 'Updated Cash'})
              .where('code', '=', '1001'))
        sql, params = qb.build()
        
        assert 'UPDATE accounts SET name = ?' in sql
        assert 'WHERE code = ?' in sql
        assert params == ['Updated Cash', '1001']
    
    def test_delete_query(self):
        """Test DELETE query."""
        qb = (QueryBuilder()
              .delete('accounts')
              .where('code', '=', '1001'))
        sql, params = qb.build()
        
        assert 'DELETE FROM accounts' in sql
        assert params == ['1001']
    
    def test_join_query(self):
        """Test JOIN query."""
        qb = (QueryBuilder()
              .select('a.code', 'a.name', 'p.name')
              .from_('accounts a')
              .join('parties p', 'a.party_id', '=', 'p.id')
              .where('a.is_active', '=', True))
        sql, params = qb.build()
        
        assert 'JOIN parties p ON a.party_id = p.id' in sql
    
    def test_order_by_limit_offset(self):
        """Test ORDER BY, LIMIT, OFFSET."""
        qb = (QueryBuilder()
              .select('*')
              .from_('accounts')
              .order_by('code', 'ASC')
              .limit(10)
              .offset(20))
        sql, params = qb.build()
        
        assert 'ORDER BY code ASC' in sql
        assert 'LIMIT 10' in sql
        assert 'OFFSET 20' in sql
    
    def test_sql_injection_protection(self):
        """Test SQL injection protection."""
        malicious_input = "'; DROP TABLE accounts; --"
        qb = (QueryBuilder()
              .select('*')
              .from_('accounts')
              .where('name', '=', malicious_input))
        sql, params = qb.build()
        
        # Should use parameterized query, not string concatenation
        assert '?' in sql
        assert params == [malicious_input]
        assert 'DROP TABLE' not in sql


class TestQueryCache:
    """Test QueryCache functionality."""
    
    def test_cache_set_get(self):
        """Test basic cache operations."""
        cache = QueryCache(max_size=100, ttl_seconds=60)
        
        cache.set('test_key', 'test_value')
        result = cache.get('test_key')
        
        assert result == 'test_value'
    
    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache = QueryCache(max_size=100, ttl_seconds=1)
        
        cache.set('short_lived', 'value')
        
        import time
        time.sleep(1.1)  # Wait for expiration
        
        result = cache.get('short_lived')
        assert result is None
    
    def test_cache_max_size_eviction(self):
        """Test LRU eviction when max size reached."""
        cache = QueryCache(max_size=3, ttl_seconds=60)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        # Add one more, should evict key1 (oldest)
        cache.set('key4', 'value4')
        
        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'
        assert cache.get('key4') == 'value4'
    
    def test_cache_clear(self):
        """Test cache clearing."""
        cache = QueryCache(max_size=100, ttl_seconds=60)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        cache.clear()
        
        assert cache.get('key1') is None
        assert cache.get('key2') is None
        assert cache.stats()['hits'] == 0
        assert cache.stats()['misses'] == 0


class TestBulkOperations:
    """Test bulk operation functionality."""
    
    def test_bulk_insert_sql_generation(self):
        """Test bulk INSERT SQL generation."""
        records = [
            {'code': '1001', 'name': 'Cash'},
            {'code': '1002', 'name': 'Bank'},
            {'code': '1003', 'name': 'Receivables'}
        ]
        
        sql, params = BulkOperations.bulk_insert('accounts', records)
        
        assert 'INSERT INTO accounts' in sql
        assert sql.count('?') == 6  # 2 fields × 3 records
        assert len(params) == 6
    
    def test_bulk_update_sql_generation(self):
        """Test bulk UPDATE SQL generation."""
        records = [
            {'id': 1, 'name': 'Updated1'},
            {'id': 2, 'name': 'Updated2'}
        ]
        
        sql, params = BulkOperations.bulk_update('accounts', records, 'id')
        
        assert 'UPDATE accounts' in sql
        assert 'WHERE id IN (?, ?)' in sql
    
    def test_bulk_delete_sql_generation(self):
        """Test bulk DELETE SQL generation."""
        ids = [1, 2, 3, 4, 5]
        
        sql, params = BulkOperations.bulk_delete('accounts', 'id', ids)
        
        assert 'DELETE FROM accounts' in sql
        assert 'WHERE id IN (?, ?, ?, ?, ?)' in sql
        assert len(params) == 5
    
    def test_empty_records_handling(self):
        """Test handling of empty record lists."""
        sql, params = BulkOperations.bulk_insert('accounts', [])
        
        assert sql == ''
        assert params == []
```

---

### File: `tests/database/test_transaction_manager.py`

```python
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
```

---

### File: `tests/database/test_migrations.py`

```python
"""Tests for MigrationManager."""
import pytest
import sqlite3
from pathlib import Path
from src.database.migration_manager import MigrationManager
from src.database.migrations.V1_0_initial_schema import V1_0InitialSchema


class TestMigrationManager:
    """Test MigrationManager functionality."""
    
    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temporary database path."""
        return tmp_path / 'test_migrations.db'
    
    @pytest.fixture
    def migration_manager(self, temp_db_path):
        """Create MigrationManager instance."""
        return MigrationManager(str(temp_db_path))
    
    def test_migration_table_creation(self, migration_manager, temp_db_path):
        """Test that migrations table is created."""
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()
        
        # Run migrations
        migration_manager.run_migrations()
        
        # Check migrations table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='schema_migrations'
        """)
        result = cursor.fetchone()
        
        assert result is not None
        conn.close()
    
    def test_run_migrations_up(self, migration_manager, temp_db_path):
        """Test running UP migrations."""
        result = migration_manager.run_migrations()
        
        assert result['success'] is True
        assert len(result['applied']) > 0
        assert result['failed'] == []
    
    def test_migration_version_tracking(self, migration_manager, temp_db_path):
        """Test that applied migrations are tracked."""
        migration_manager.run_migrations()
        
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
        versions = [row[0] for row in cursor.fetchall()]
        
        assert 'V1_0' in versions
        conn.close()
    
    def test_rollback_migration(self, migration_manager, temp_db_path):
        """Test rolling back a migration."""
        # Apply migrations
        migration_manager.run_migrations()
        
        # Rollback last migration
        result = migration_manager.rollback('V1_0')
        
        assert result['success'] is True
        assert result['rolled_back'] == ['V1_0']
    
    def test_rollback_to_version(self, migration_manager, temp_db_path):
        """Test rolling back to specific version."""
        # Apply migrations
        migration_manager.run_migrations()
        
        # Rollback to before V1_0 (should rollback everything)
        result = migration_manager.rollback_to('V0_0')
        
        assert result['success'] is True
    
    def test_migration_status(self, migration_manager, temp_db_path):
        """Test getting migration status."""
        # Before running migrations
        status_before = migration_manager.get_status()
        assert status_before['current_version'] is None
        
        # Run migrations
        migration_manager.run_migrations()
        
        # After running migrations
        status_after = migration_manager.get_status()
        assert status_after['current_version'] == 'V1_0'
        assert status_after['total_applied'] > 0
    
    def test_verify_migrations(self, migration_manager, temp_db_path):
        """Test migration verification."""
        # Run migrations
        migration_manager.run_migrations()
        
        # Verify
        result = migration_manager.verify_migrations()
        
        assert result['success'] is True
        assert len(result['missing_tables']) == 0
        assert len(result['missing_indexes']) == 0
    
    def test_dry_run_migration(self, migration_manager, temp_db_path):
        """Test dry run of migrations."""
        result = migration_manager.run_migrations(dry_run=True)
        
        assert result['success'] is True
        assert len(result['to_apply']) > 0
        assert len(result['applied']) == 0  # Nothing actually applied
    
    def test_generate_migration_template(self, migration_manager, tmp_path):
        """Test generating migration template."""
        template_path = migration_manager.generate_migration(
            'test_feature',
            output_dir=str(tmp_path)
        )
        
        assert Path(template_path).exists()
        
        content = Path(template_path).read_text()
        assert 'def up(self, cursor):' in content
        assert 'def down(self, cursor):' in content
```

---

## Running Tests with Different Options

### Verbose Output
```bash
pytest tests/database/ -v
```

### Show Local Variables on Failure
```bash
pytest tests/database/ -l
```

### Stop on First Failure
```bash
pytest tests/database/ -x
```

### Run Only Failed Tests (from previous run)
```bash
pytest tests/database/ --lf
```

### Run Tests Matching Pattern
```bash
pytest tests/database/ -k "connection"
pytest tests/database/ -k "cache"
pytest tests/database/ -k "bulk"
```

### Parallel Execution (faster)
```bash
pip install pytest-xdist
pytest tests/database/ -n auto
```

### Coverage Reports
```bash
# Terminal report
pytest tests/database/ --cov=src/database --cov-report=term-missing

# HTML report (open in browser)
pytest tests/database/ --cov=src/database --cov-report=html
# Then open: rebuildbop/htmlcov/index.html

# XML report (for CI/CD)
pytest tests/database/ --cov=src/database --cov-report=xml
```

### Performance Testing
```bash
# Run performance benchmarks
pytest tests/database/ -m performance --runslow

# With profiling
pip install pytest-profiling
pytest tests/database/ --profile
```

---

## Expected Test Results

### Passing Tests Example
```
tests/database/test_connection_pool.py::test_connection_pool_creation PASSED
tests/database/test_connection_pool.py::test_borrow_return_connection PASSED
tests/database/test_connection_pool.py::test_max_connections_limit PASSED
...
tests/database/test_query_builder.py::test_select_basic PASSED
tests/database/test_query_builder.py::test_sql_injection_protection PASSED
...
tests/database/test_transaction_manager.py::test_transaction_begin_commit PASSED
...
tests/database/test_migrations.py::test_run_migrations_up PASSED
...

==================== 45 passed in 2.34s ====================
```

### Coverage Report Example
```
Name                                      Stmts   Miss  Cover   Missing
-----------------------------------------------------------------------
src/database/connection_pool.py             245      12    95%   145-148, 201-205
src/database/query_builder.py               312       8    97%   89-92, 156
src/database/transaction_manager.py         198       5    97%   112-115
src/database/migration_manager.py           156       3    98%   78-80
-----------------------------------------------------------------------
TOTAL                                       911      28    97%
```

---

## Troubleshooting Common Issues

### Issue: Import Errors
```bash
# Make sure you're in the rebuildbop directory
cd /workspace/rebuildbop

# Ensure src is in PYTHONPATH
export PYTHONPATH=/workspace/rebuildbop/src:$PYTHONPATH
```

### Issue: SQLite Cloud Connection Failed
```bash
# Use local SQLite for testing
export USE_LOCAL_SQLITE=true

# Or skip database tests requiring connection
pytest tests/database/ -m "not integration"
```

### Issue: Tests Running Slow
```bash
# Skip slow tests
pytest tests/database/ -m "not slow"

# Run in parallel
pytest tests/database/ -n 4
```

### Issue: Coverage Not Showing
```bash
# Ensure __init__.py files exist
touch src/database/__init__.py
touch src/__init__.py

# Re-run with --cov flag
pytest tests/database/ --cov=src/database
```

---

## Next Phase Testing

After completing Phase 3 (Repository Layer), run:
```bash
# Test repositories
pytest tests/repositories/ -v --cov=src/repositories

# Test all layers together
pytest tests/database/ tests/repositories/ -v
```

After completing Phase 4 (Service Layer), run:
```bash
# Test services
pytest tests/services/ -v --cov=src/services

# Integration tests
pytest tests/integration/ -v
```

---

## Continuous Testing Workflow

```bash
# Watch mode (auto-rerun on file changes)
pip install pytest-watch
ptw -- tests/database/

# Or use entr
brew install entr
find src/database tests/database -name "*.py" | entr -c pytest tests/database/
```

---

## Summary Commands by Phase

| Phase | Command | Coverage Target |
|-------|---------|----------------|
| Phase 2 (Database) | `pytest tests/database/ -v` | 90%+ |
| Phase 3 (Repository) | `pytest tests/repositories/ -v` | 90%+ |
| Phase 4 (Service) | `pytest tests/services/ -v` | 90%+ |
| Phase 5 (Controller) | `pytest tests/controllers/ -v` | 90%+ |
| All Layers | `pytest tests/ -v` | 90%+ |
| Performance | `pytest tests/performance/ -m performance --runslow` | N/A |

Good luck with testing! 🚀
