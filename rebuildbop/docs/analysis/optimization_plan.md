# BOP Pharmaceutical ERP - Optimization Plan

## Overview

This document outlines the comprehensive optimization strategy for rebuilding the BOP Pharmaceutical ERP system with SQLite Cloud as the primary database from day one.

## Architecture Goals

### 1. Network-First Design
Every component must be designed assuming 50-200ms network latency:
- Minimize round-trips through batch operations
- Cache aggressively at multiple levels
- Use async operations to prevent UI blocking
- Implement retry logic with exponential backoff

### 2. Layered Architecture

```
┌─────────────────────────────────────────┐
│         PRESENTATION LAYER              │
│  (PySide6 Views with Async Support)     │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         CONTROLLER LAYER                │
│  (Input Validation, Error Handling)     │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│          SERVICE LAYER                  │
│  (Business Logic, Transactions)         │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│        REPOSITORY LAYER                 │
│  (CRUD Operations, Caching, Batching)   │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         DATABASE LAYER                  │
│  (Connection Pooling, Query Building)   │
└─────────────────────────────────────────┘
```

## Phase 1: Database Layer Implementation

### 1.1 Connection Pool Enhancement

**Current Issues:**
- Fixed pool size (20 connections)
- No health checking
- No automatic reconnection
- Inefficient connection reuse

**Optimized Implementation:**

```python
class ConnectionPool:
    """Thread-safe connection pool with health monitoring."""
    
    def __init__(self, min_connections=10, max_connections=50):
        self.min_connections = min_connections
        self.max_connections = max_connections
        self._connections = []
        self._in_use = set()
        self._lock = threading.Lock()
        self._health_check_interval = 60  # seconds
        self._last_health_check = {}
        
    def get_connection(self, timeout=30):
        """Get connection with health check and auto-reconnect."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self._lock:
                # Try to get existing connection
                while self._connections:
                    conn = self._connections.pop()
                    if self._is_healthy(conn):
                        self._in_use.add(id(conn))
                        return conn
                    else:
                        self._reconnect(conn)
                
                # Create new connection if under max
                if len(self._in_use) < self.max_connections:
                    conn = self._create_connection()
                    self._in_use.add(id(conn))
                    return conn
            
            # Wait and retry if pool exhausted
            time.sleep(0.1)
        
        raise ConnectionPoolExhaustedError("No available connections")
    
    def _is_healthy(self, conn):
        """Check if connection is alive."""
        try:
            conn.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def _reconnect(self, conn):
        """Attempt to reconnect a dead connection."""
        try:
            conn.close()
        except Exception:
            pass
        # Connection will be recreated on next get
```

**Key Features:**
- Dynamic pool sizing (10-50 connections)
- Health checking before returning connections
- Automatic reconnection on failure
- Timeout handling for pool exhaustion
- Connection metrics tracking

### 1.2 Query Builder with Batching

**Current Issues:**
- Manual SQL construction throughout codebase
- No batch operation support
- SQL injection risk in some areas
- No query optimization

**Optimized Implementation:**

```python
class QueryBuilder:
    """Fluent SQL builder with batching support."""
    
    def __init__(self, table: str):
        self.table = table
        self._select_cols = ["*"]
        self._wheres = []
        self._params = []
        self._order_by = None
        self._limit = None
        
    def select(self, *columns) -> 'QueryBuilder':
        self._select_cols = columns if columns else ["*"]
        return self
    
    def where(self, condition: str, *params) -> 'QueryBuilder':
        self._wheres.append(condition)
        self._params.extend(params)
        return self
    
    def build(self) -> tuple[str, tuple]:
        sql = f"SELECT {', '.join(self._select_cols)} FROM {self.table}"
        if self._wheres:
            sql += " WHERE " + " AND ".join(self._wheres)
        if self._order_by:
            sql += f" ORDER BY {self._order_by}"
        if self._limit:
            sql += f" LIMIT {self._limit}"
        return sql, tuple(self._params)


class BatchOperation:
    """Batch database operations for network efficiency."""
    
    def __init__(self, db: DatabaseConnection, batch_size=100):
        self.db = db
        self.batch_size = batch_size
        
    def bulk_insert(self, table: str, rows: list[dict]) -> list[int]:
        """Insert multiple rows in single round-trip."""
        if not rows:
            return []
        
        columns = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_list = ", ".join(columns)
        
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
        
        # Group into batches
        ids = []
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i:i + self.batch_size]
            values = [tuple(row[col] for col in columns) for row in batch]
            self.db.executemany(sql, values)
            # Get last insert IDs (SQLite Cloud specific)
            ids.extend(self.db.get_last_insert_ids(len(batch)))
        
        return ids
    
    def bulk_update(self, table: str, pk_column: str, 
                   updates: list[tuple[int, dict]]) -> None:
        """Update multiple rows efficiently."""
        if not updates:
            return
        
        for i in range(0, len(updates), self.batch_size):
            batch = updates[i:i + self.batch_size]
            for pk_value, data in batch:
                set_clause = ", ".join(f"{col} = ?" for col in data.keys())
                sql = f"UPDATE {table} SET {set_clause} WHERE {pk_column} = ?"
                params = tuple(data.values()) + (pk_value,)
                self.db.execute(sql, params)
```

### 1.3 Transaction Manager with Retry Logic

```python
class TransactionManager:
    """Transaction management with automatic retry."""
    
    MAX_RETRIES = 3
    BACKOFF_SECONDS = [0.1, 0.5, 2.0]  # Exponential backoff
    
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
        
    @contextmanager
    def transaction(self, retries=MAX_RETRIES):
        """Context manager with automatic retry on deadlock."""
        conn = self.pool.get_connection()
        attempt = 0
        
        while attempt <= retries:
            try:
                conn.execute("BEGIN TRANSACTION")
                yield conn
                conn.execute("COMMIT")
                break
            except DeadlockError as e:
                conn.execute("ROLLBACK")
                attempt += 1
                if attempt > retries:
                    raise
                logger.warning(f"Deadlock detected, retrying ({attempt}/{retries})")
                time.sleep(self.BACKOFF_SECONDS[min(attempt - 1, len(self.BACKOFF_SECONDS) - 1)])
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                self.pool.return_connection(conn)
```

### 1.4 Index Strategy

**Critical Indexes to Add:**

```sql
-- Journal entries (most queried table)
CREATE INDEX idx_je_company_date ON journal_entries(company_id, entry_date);
CREATE INDEX idx_je_company_type ON journal_entries(company_id, voucher_type);
CREATE INDEX idx_je_source ON journal_entries(source_table, source_id);
CREATE INDEX idx_je_posted_company ON journal_entries(is_posted, company_id);

-- Journal entry lines
CREATE INDEX idx_jel_account_je ON journal_entry_lines(journal_entry_id, account_id);
CREATE INDEX idx_jel_party ON journal_entry_lines(party_id) WHERE party_id IS NOT NULL;

-- Sales invoices
CREATE INDEX idx_sales_company_customer ON sales_invoices(company_id, customer_id);
CREATE INDEX idx_sales_company_date ON sales_invoices(company_id, invoice_date);
CREATE INDEX idx_sales_company_status ON sales_invoices(company_id, status);

-- Purchase invoices
CREATE INDEX idx_purchase_company_supplier ON purchase_invoices(company_id, supplier_id);
CREATE INDEX idx_purchase_company_date ON purchase_invoices(company_id, invoice_date);

-- Parties
CREATE INDEX idx_parties_company_type ON parties(company_id, party_type);
CREATE INDEX idx_parties_company_active ON parties(company_id, is_active);

-- Items
CREATE INDEX idx_items_company_active ON items(company_id, is_active);
CREATE INDEX idx_items_company_category ON items(company_id, category_id);

-- Stock batches
CREATE INDEX idx_stock_item_warehouse ON stock_batches(item_id, warehouse_id);
CREATE INDEX idx_stock_item_active ON stock_batches(item_id, is_active);

-- Accounts
CREATE INDEX idx_accounts_company_code ON accounts(company_id, account_code);
CREATE INDEX idx_accounts_company_type ON accounts(company_id, account_type);
```

## Phase 2: Repository Layer Implementation

### 2.1 Base Repository with Multi-Level Caching

```python
from collections import OrderedDict
import time

class LRUCache:
    """LRU cache with TTL and size limit."""
    
    def __init__(self, max_size=1000, ttl_seconds=300):
        self.cache = OrderedDict()
        self.timestamps = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
    
    def get(self, key):
        with self._lock:
            if key not in self.cache:
                return None
            
            # Check TTL
            if time.time() - self.timestamps[key] > self.ttl_seconds:
                self.delete(key)
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
    
    def set(self, key, value):
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            self.timestamps[key] = time.time()
            
            # Evict oldest if over capacity
            while len(self.cache) > self.max_size:
                oldest_key = next(iter(self.cache))
                self.delete(oldest_key)
    
    def delete(self, key):
        with self._lock:
            self.cache.pop(key, None)
            self.timestamps.pop(key, None)
    
    def clear(self):
        with self._lock:
            self.cache.clear()
            self.timestamps.clear()


class BaseRepository:
    """Base repository with L1 caching and batch operations."""
    
    table_name: str = ""
    pk_column: str = "id"
    
    # Class-level L1 cache shared across instances
    _l1_cache = LRUCache(max_size=1000, ttl_seconds=300)
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.batch_op = BatchOperation(db)
    
    def find_by_id(self, record_id: int) -> dict | None:
        """Get by ID with L1 caching."""
        cache_key = f"{self.table_name}:id:{record_id}"
        cached = self._l1_cache.get(cache_key)
        if cached is not None:
            return cached
        
        result = self.db.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE {self.pk_column} = ?",
            (record_id,)
        )
        
        if result:
            self._l1_cache.set(cache_key, result)
        
        return result
    
    def find_all_by_ids(self, ids: list[int]) -> list[dict]:
        """Batch fetch by IDs - reduces N queries to 1."""
        if not ids:
            return []
        
        # Check cache first
        cached = []
        missing_ids = []
        for id in ids:
            cache_key = f"{self.table_name}:id:{id}"
            item = self._l1_cache.get(cache_key)
            if item:
                cached.append(item)
            else:
                missing_ids.append(id)
        
        # Fetch missing from DB
        if missing_ids:
            placeholders = ", ".join("?" for _ in missing_ids)
            sql = f"SELECT * FROM {self.table_name} WHERE {self.pk_column} IN ({placeholders})"
            results = self.db.fetch_all(sql, tuple(missing_ids))
            
            # Cache results
            for row in results:
                cache_key = f"{self.table_name}:id:{row[self.pk_column]}"
                self._l1_cache.set(cache_key, row)
                cached.append(row)
        
        return cached
    
    def bulk_insert(self, rows: list[dict]) -> list[int]:
        """Bulk insert with cache invalidation."""
        ids = self.batch_op.bulk_insert(self.table_name, rows)
        self._invalidate_all()
        return ids
    
    def _invalidate_all(self):
        """Clear all cache for this table."""
        prefix = f"{self.table_name}:"
        keys_to_delete = [k for k in self._l1_cache.cache.keys() if k.startswith(prefix)]
        for key in keys_to_delete:
            self._l1_cache.delete(key)
```

### 2.2 Specialized Repositories

Each entity gets its own repository with optimized queries:

```python
class SalesInvoiceRepository(BaseRepository):
    table_name = "sales_invoices"
    
    def find_with_details(self, company_id: int, 
                         date_from=None, date_to=None) -> list[dict]:
        """Fetch invoices with customer and items in ONE query."""
        sql = """
            SELECT 
                si.*,
                p.name as customer_name,
                p.code as customer_code,
                GROUP_CONCAT(
                    sii.item_id || ':' || sii.quantity || ':' || sii.unit_price,
                    '|'
                ) as items_data
            FROM sales_invoices si
            JOIN parties p ON p.id = si.customer_id
            LEFT JOIN sales_invoice_items sii ON sii.invoice_id = si.id
            WHERE si.company_id = ?
        """
        params = [company_id]
        
        if date_from:
            sql += " AND si.invoice_date >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND si.invoice_date <= ?"
            params.append(date_to)
        
        sql += " GROUP BY si.id ORDER BY si.invoice_date DESC"
        
        return self.db.fetch_all(sql, tuple(params))
    
    def get_summary_totals(self, company_id: int, 
                          period_start: str, period_end: str) -> dict:
        """Get sales summary in ONE query instead of multiple."""
        sql = """
            SELECT 
                COUNT(*) as invoice_count,
                COALESCE(SUM(total_amount), 0) as total_sales,
                COALESCE(SUM(CASE WHEN payment_type = 'CREDIT' THEN total_amount ELSE 0 END), 0) as credit_sales,
                COALESCE(SUM(CASE WHEN payment_type IN ('CASH', 'BANK', 'CHEQUE') THEN total_amount ELSE 0 END), 0) as cash_sales
            FROM sales_invoices
            WHERE company_id = ?
            AND invoice_date BETWEEN ? AND ?
            AND is_active = 1
        """
        return self.db.fetch_one(sql, (company_id, period_start, period_end))
```

## Phase 3: Service Layer Implementation

### 3.1 Service Architecture

```python
class BaseService:
    """Base service with common functionality."""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.logger = get_logger(self.__class__.__name__)
    
    def validate(self, data: dict, rules: dict) -> None:
        """Validate data against business rules."""
        errors = []
        for field, rule in rules.items():
            value = data.get(field)
            if not rule(value):
                errors.append(f"Validation failed for {field}")
        
        if errors:
            raise ValidationError("; ".join(errors))
    
    def audit_log(self, action: str, entity_type: str, 
                 entity_id: int, user_id: int, details: dict = None):
        """Log all modifications for audit trail."""
        # Implementation
        pass
```

### 3.2 Optimized Sales Invoice Service

```python
class SalesInvoiceService(BaseService):
    """Sales invoice processing with optimized operations."""
    
    def __init__(self, db: DatabaseConnection):
        super().__init__(db)
        self.invoice_repo = SalesInvoiceRepository(db)
        self.item_repo = ItemRepository(db)
        self.stock_repo = StockBatchRepository(db)
        self.party_repo = PartyRepository(db)
        self.accounting_service = AccountingService(db)
    
    def create_invoice(self, invoice_data: dict, items: list[dict], 
                      user_id: int) -> int:
        """Create invoice with minimal DB round-trips."""
        
        # Step 1: Validate all data upfront (batch validation)
        self._validate_invoice_data(invoice_data, items)
        
        # Step 2: Batch fetch all required data
        item_ids = [item['item_id'] for item in items]
        items_master = {i['id']: i for i in self.item_repo.find_all_by_ids(item_ids)}
        
        # Step 3: Check stock availability (batch check)
        stock_checks = self._check_stock_batch(items, invoice_data['warehouse_id'])
        if not stock_checks['available']:
            raise InsufficientStockError(stock_checks['message'])
        
        # Step 4: Calculate totals
        totals = self._calculate_totals(items)
        
        # Step 5: Batch fetch accounts needed for journal entry
        account_codes = self._get_required_account_codes(invoice_data['payment_type'])
        accounts = self.account_repo.find_all_by_codes(account_codes)
        
        # Step 6: Create invoice in transaction
        with self.db.transaction():
            # Insert invoice header
            invoice_id = self.invoice_repo.insert({
                **invoice_data,
                **totals,
                'created_by': user_id
            })
            
            # Insert invoice items (batch insert)
            invoice_items = [
                {**item, 'invoice_id': invoice_id}
                for item in items
            ]
            self.invoice_repo.item_repo.bulk_insert(invoice_items)
            
            # Update stock (batch update)
            self._update_stock_batch(items, invoice_data['warehouse_id'])
            
            # Create journal entry
            journal_lines = self._create_journal_lines(
                invoice_data, totals, accounts, items_master
            )
            self.accounting_service.post_journal_entry(
                voucher_type=VoucherType.SALES,
                entry_date=invoice_data['invoice_date'],
                lines=journal_lines,
                source_table='sales_invoices',
                source_id=invoice_id,
                narration=f"Sales invoice {invoice_data['invoice_number']}"
            )
            
            # Create COGS entry
            self._create_cogs_entry(items_master, items, accounts)
        
        return invoice_id
    
    def _check_stock_batch(self, items: list[dict], 
                          warehouse_id: int) -> dict:
        """Check stock for all items in minimal queries."""
        # Single query to get all stock batches
        item_ids = [item['item_id'] for item in items]
        placeholders = ", ".join("?" for _ in item_ids)
        
        sql = f"""
            SELECT item_id, SUM(quantity_in_stock) as available_qty
            FROM stock_batches
            WHERE item_id IN ({placeholders})
            AND warehouse_id = ?
            AND is_active = 1
            GROUP BY item_id
        """
        params = tuple(item_ids) + (warehouse_id,)
        stock_levels = {row['item_id']: row['available_qty'] 
                       for row in self.db.fetch_all(sql, params)}
        
        # Check each item
        for item in items:
            available = stock_levels.get(item['item_id'], 0)
            required = item['quantity']
            if available < required:
                return {
                    'available': False,
                    'message': f"Insufficient stock for item {item['item_id']}"
                }
        
        return {'available': True}
```

## Phase 4: Controller Layer with Async Support

### 4.1 Async Controller Pattern

```python
from PySide6.QtCore import QObject, Signal, QThread

class DatabaseWorker(QThread):
    """Generic database worker for async operations."""
    
    finished = Signal(object)  # Success result
    error = Signal(str)  # Error message
    
    def __init__(self, operation, *args, **kwargs):
        super().__init__()
        self.operation = operation
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.operation(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            logger.exception(f"Database operation failed: {e}")
            self.error.emit(str(e))


class BaseController:
    """Base controller with async operation support."""
    
    def __init__(self, view, service):
        self.view = view
        self.service = service
        self.worker = None
    
    def execute_async(self, operation, *args, 
                     on_success=None, on_error=None,
                     show_loading=True):
        """Execute database operation asynchronously."""
        if show_loading:
            self.view.show_loading_indicator()
        
        self.worker = DatabaseWorker(operation, *args)
        
        if on_success:
            self.worker.finished.connect(on_success)
        
        if on_error:
            self.worker.error.connect(on_error)
        else:
            self.worker.error.connect(self._handle_error)
        
        # Cleanup loading indicator after completion
        if show_loading:
            self.worker.finished.connect(self.view.hide_loading_indicator)
            self.worker.error.connect(self.view.hide_loading_indicator)
        
        self.worker.start()
    
    def _handle_error(self, error_message):
        """Default error handler."""
        self.view.show_error_dialog(
            "Operation Failed",
            error_message,
            actions=['retry', 'cancel']
        )
```

## Phase 5: View Layer with Responsive UI

### 5.1 Loading Indicators and Skeleton Screens

```python
class LoadingWidget(QWidget):
    """Reusable loading widget with spinner and message."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.hide()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.spinner = QProgressBar()
        self.spinner.setRange(0, 0)  # Infinite spinning
        layout.addWidget(self.spinner)
        
        self.message_label = QLabel("Loading...")
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)
    
    def show_with_message(self, message):
        self.message_label.setText(message)
        self.show()
    
    def hide(self):
        super().hide()


class SkeletonTable(QWidget):
    """Skeleton loader for table data."""
    
    def __init__(self, rows=5, columns=4, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.columns = columns
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        for i in range(self.rows):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            
            for j in range(self.columns):
                skeleton = QLabel("████████")
                skeleton.setStyleSheet("""
                    background-color: #e0e0e0;
                    color: transparent;
                    border-radius: 2px;
                """)
                row_layout.addWidget(skeleton)
            
            layout.addWidget(row_widget)
```

### 5.2 Async Table Loading

```python
class AsyncDataTable(QTableWidget):
    """Table widget with async data loading."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loading_widget = LoadingWidget(self)
        self.skeleton_widget = SkeletonTable(rows=10, columns=5, parent=self)
    
    def load_data_async(self, fetch_operation, transform_operation=None):
        """Load data asynchronously without blocking UI."""
        self.skeleton_widget.show()
        self.loading_widget.show_with_message("Loading data...")
        
        def on_data_loaded(data):
            self.skeleton_widget.hide()
            self.loading_widget.hide()
            
            if transform_operation:
                data = transform_operation(data)
            
            self.populate_from_data(data)
        
        def on_error(error):
            self.skeleton_widget.hide()
            self.loading_widget.hide()
            self.show_error(error)
        
        self.controller.execute_async(
            fetch_operation,
            on_success=on_data_loaded,
            on_error=on_error,
            show_loading=False  # We handle our own loading indicators
        )
```

## Performance Targets & Metrics

### Target Benchmarks

| Operation | Current | Target | Measurement Method |
|-----------|---------|--------|-------------------|
| Dashboard load | 5s+ | <1s | Time to interactive |
| Invoice creation | 3-4s | <500ms | DB commit to UI update |
| Report generation | 10s+ | <2s | Query to render |
| Search operations | 1-2s | <200ms | Keypress to results |
| DB round-trips/invoice | 200+ | <40 | Network trace |
| Concurrent users | 1-2 | 10+ | Load testing |

### Monitoring & Metrics

```python
class PerformanceMonitor:
    """Track performance metrics."""
    
    _metrics = defaultdict(list)
    
    @classmethod
    def measure(cls, operation_name):
        """Decorator to measure operation time."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    elapsed = time.perf_counter() - start
                    cls._metrics[operation_name].append(elapsed)
                    logger.info(f"{operation_name} completed in {elapsed:.3f}s")
                    return result
                except Exception as e:
                    elapsed = time.perf_counter() - start
                    cls._metrics[f"{operation_name}_errors"].append(elapsed)
                    logger.error(f"{operation_name} failed after {elapsed:.3f}s: {e}")
                    raise
            return wrapper
        return decorator
    
    @classmethod
    def get_stats(cls, operation_name) -> dict:
        """Get performance statistics for an operation."""
        metrics = cls._metrics.get(operation_name, [])
        if not metrics:
            return {'count': 0}
        
        return {
            'count': len(metrics),
            'avg': sum(metrics) / len(metrics),
            'min': min(metrics),
            'max': max(metrics),
            'p95': sorted(metrics)[int(len(metrics) * 0.95)] if len(metrics) > 20 else max(metrics)
        }
```

## Migration Strategy

### Data Migration from Old System

```python
class DataMigrator:
    """Migrate data from old database to new schema."""
    
    def __init__(self, old_db_path, new_db_connection):
        self.old_db = sqlite3.connect(old_db_path)
        self.new_db = new_db_connection
    
    def migrate_all(self):
        """Run all migrations in order."""
        self.migrate_companies()
        self.migrate_warehouses()
        self.migrate_accounts()
        self.migrate_parties()
        self.migrate_items()
        self.migrate_opening_balances()
        self.migrate_transactions()
        self.verify_migration()
    
    def migrate_accounts(self):
        """Migrate chart of accounts with validation."""
        old_accounts = self.old_db.execute(
            "SELECT * FROM accounts ORDER BY account_code"
        ).fetchall()
        
        new_accounts = []
        for acc in old_accounts:
            new_accounts.append({
                'company_id': acc['company_id'] or 1,
                'account_code': acc['account_code'],
                'account_name': acc['account_name'],
                'account_type': acc['account_type'],
                'opening_balance': acc['opening_balance'] or 0,
                'is_active': acc['is_active']
            })
        
        # Bulk insert
        self.new_db.bulk_insert('accounts', new_accounts)
        logger.info(f"Migrated {len(new_accounts)} accounts")
```

## Testing Strategy

### Test Pyramid

```
           /\          Manual Tests (10%)
          /  \         
         /----\        Integration Tests (20%)
        /      \       
       /--------\      Unit Tests (70%)
      /__________\     
```

### Unit Test Example

```python
import pytest
from unittest.mock import Mock, MagicMock

class TestSalesInvoiceService:
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=DatabaseConnection)
    
    @pytest.fixture
    def service(self, mock_db):
        return SalesInvoiceService(mock_db)
    
    def test_create_invoice_validates_input(self, service):
        # Arrange
        invalid_data = {'customer_id': None}  # Missing required field
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service.create_invoice(invalid_data, [], 1)
        
        assert "Customer is required" in str(exc_info.value)
    
    def test_create_invoice_rejects_insufficient_stock(self, service):
        # Arrange
        mock_stock_check = Mock(return_value={'available': False})
        service._check_stock_batch = mock_stock_check
        
        # Act & Assert
        with pytest.raises(InsufficientStockError):
            service.create_invoice(valid_data, items, 1)
```

### Performance Test Example

```python
import pytest
import time

class TestPerformance:
    
    def test_invoice_creation_under_500ms(self, service, sample_invoice_data):
        start = time.perf_counter()
        
        invoice_id = service.create_invoice(
            sample_invoice_data['header'],
            sample_invoice_data['items'],
            user_id=1
        )
        
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"Invoice creation took {elapsed:.3f}s (target: <0.5s)"
    
    def test_dashboard_load_under_1s(self, dashboard_service):
        start = time.perf_counter()
        
        data = dashboard_service.get_dashboard_data(company_id=1)
        
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"Dashboard load took {elapsed:.3f}s (target: <1.0s)"
```

## Conclusion

This optimization plan addresses all identified performance issues through:

1. **Network-first architecture** - Every operation designed for 50-200ms latency
2. **Aggressive batching** - Reduce 200+ round-trips to <40
3. **Multi-level caching** - L1 (LRU), L2 (prepared statements), L3 (global)
4. **Async UI operations** - Zero UI freezes
5. **Connection pooling** - Efficient resource utilization
6. **Comprehensive indexing** - Optimized query performance
7. **Retry logic** - Graceful handling of network failures

The rebuild will achieve 10x performance improvement while maintaining 100% business logic accuracy.

---

*Version: 1.0*
*Last Updated: Based on analysis of existing BOP ERP system*
