"""
Transaction Manager with Retry Logic

Provides robust transaction management for SQLite Cloud with:
- Savepoint support for nested transactions
- Automatic retry with exponential backoff
- Deadlock detection and resolution
- Rollback on failure

Performance Targets:
- Transaction start: < 5ms
- Commit/rollback: < 10ms
- Retry success rate: > 95% within 3 attempts
"""

import sqlite3
import threading
import time
import logging
from typing import Optional, Callable, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from contextlib import contextmanager
import random

logger = logging.getLogger(__name__)


class TransactionState(Enum):
    """Transaction lifecycle states"""
    NONE = "none"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class TransactionMetrics:
    """Track transaction metrics"""
    total_started: int = 0
    total_committed: int = 0
    total_rolled_back: int = 0
    total_retries: int = 0
    successful_retries: int = 0
    deadlock_count: int = 0
    avg_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    
    _durations: List[float] = field(default_factory=list)
    
    def record_duration(self, duration_ms: float):
        """Record transaction duration"""
        self._durations.append(duration_ms)
        if len(self._durations) > 100:
            self._durations.pop(0)
        self.avg_duration_ms = sum(self._durations) / len(self._durations)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_started': self.total_started,
            'total_committed': self.total_committed,
            'total_rolled_back': self.total_rolled_back,
            'total_retries': self.total_retries,
            'successful_retries': self.successful_retries,
            'deadlock_count': self.deadlock_count,
            'retry_success_rate': f"{(self.successful_retries / max(self.total_retries, 1)) * 100:.1f}%",
            'avg_duration_ms': round(self.avg_duration_ms, 2),
            'max_duration_ms': round(self.max_duration_ms, 2)
        }


class TransactionError(Exception):
    """Base exception for transaction errors"""
    pass


class DeadlockError(TransactionError):
    """Raised when a deadlock is detected"""
    pass


class RetryExhaustedError(TransactionError):
    """Raised when all retry attempts are exhausted"""
    pass


class Savepoint:
    """Represents a transaction savepoint"""
    
    def __init__(self, name: str, connection: sqlite3.Connection):
        """
        Create a savepoint
        
        Args:
            name: Savepoint name
            connection: Database connection
        """
        self.name = name
        self.conn = connection
        self.created_at = datetime.now()
        
        # Create savepoint
        self.conn.execute(f"SAVEPOINT {name}")
        logger.debug(f"Savepoint '{name}' created")
    
    def rollback(self):
        """Rollback to this savepoint"""
        self.conn.execute(f"ROLLBACK TO SAVEPOINT {self.name}")
        logger.debug(f"Rolled back to savepoint '{self.name}'")
    
    def release(self):
        """Release (destroy) this savepoint"""
        self.conn.execute(f"RELEASE SAVEPOINT {self.name}")
        logger.debug(f"Savepoint '{self.name}' released")


class TransactionManager:
    """
    Manage database transactions with advanced features
    
    Features:
    - Nested transactions via savepoints
    - Automatic retry on transient failures
    - Deadlock detection
    - Context manager support
    - Metrics collection
    
    Usage:
        tm = TransactionManager(pool)
        
        # Simple transaction
        with tm.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO accounts ...')
        
        # With retry logic
        @tm.retry_on_failure(max_attempts=3)
        def update_balance(account_id, amount):
            with tm.transaction() as conn:
                # ... operations
        
        # Nested transactions
        with tm.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT ...')
            
            with tm.savepoint('nested') as sp:
                cursor.execute('UPDATE ...')
                # If this fails, only UPDATE is rolled back
    """
    
    # Transient errors that should trigger retry
    TRANSIENT_ERRORS = (
        sqlite3.OperationalError,
        sqlite3.DatabaseError,
    )
    
    # Error messages indicating transient failures
    TRANSIENT_PATTERNS = [
        'database is locked',
        'unable to open database file',
        'disk I/O error',
        'protocol error',
        'network timeout',
        'connection reset',
        'deadlock'
    ]
    
    def __init__(
        self,
        connection_pool: Any,  # ConnectionPool type
        max_retries: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 5.0,
        jitter: bool = True,
        deadlock_timeout: float = 1.0
    ):
        """
        Initialize transaction manager
        
        Args:
            connection_pool: Connection pool instance
            max_retries: Maximum retry attempts
            base_delay: Base delay between retries (seconds)
            max_delay: Maximum delay between retries
            jitter: Add randomness to prevent thundering herd
            deadlock_timeout: Timeout for deadlock detection
        """
        self.pool = connection_pool
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.deadlock_timeout = deadlock_timeout
        
        # Thread-local storage for transaction state
        self._local = threading.local()
        
        # Metrics
        self.metrics = TransactionMetrics()
        
        # Active transactions tracking
        self._active_transactions: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def _get_thread_state(self) -> Dict[str, Any]:
        """Get or create thread-local transaction state"""
        if not hasattr(self._local, 'transaction'):
            self._local.transaction = {
                'active': False,
                'savepoints': [],
                'depth': 0,
                'start_time': None
            }
        return self._local.transaction
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay with exponential backoff and optional jitter
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            jitter_range = delay * 0.2  # 20% jitter
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    def _is_transient_error(self, error: Exception) -> bool:
        """
        Check if error is transient and should trigger retry
        
        Args:
            error: Exception to check
            
        Returns:
            True if error is transient
        """
        error_msg = str(error).lower()
        
        # Check error message patterns
        for pattern in self.TRANSIENT_PATTERNS:
            if pattern in error_msg:
                return True
        
        # Check for deadlock specifically
        if isinstance(error, sqlite3.OperationalError) and 'lock' in error_msg:
            return True
        
        return False
    
    def _is_deadlock(self, error: Exception) -> bool:
        """Check if error indicates a deadlock"""
        error_msg = str(error).lower()
        return 'deadlock' in error_msg or ('lock' in error_msg and 'timeout' in error_msg)
    
    def _register_transaction(self, conn_id: int):
        """Register active transaction for monitoring"""
        with self._lock:
            self._active_transactions[conn_id] = {
                'start_time': datetime.now(),
                'thread_id': threading.current_thread().ident,
                'savepoints': []
            }
    
    def _unregister_transaction(self, conn_id: int):
        """Unregister completed transaction"""
        with self._lock:
            if conn_id in self._active_transactions:
                del self._active_transactions[conn_id]
    
    def _add_savepoint_to_transaction(self, conn_id: int, savepoint_name: str):
        """Track savepoint in active transaction"""
        with self._lock:
            if conn_id in self._active_transactions:
                self._active_transactions[conn_id]['savepoints'].append(savepoint_name)
    
    @contextmanager
    def transaction(self, name: Optional[str] = None):
        """
        Context manager for database transactions
        
        Args:
            name: Optional transaction name for logging
            
        Yields:
            sqlite3.Connection
            
        Example:
            with tm.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO accounts ...')
                # Automatically commits on exit, rolls back on exception
        """
        state = self._get_thread_state()
        conn = None
        start_time = time.time()
        
        try:
            # Get connection from pool
            pooled = self.pool.get_connection()
            conn = pooled.connection
            conn_id = id(conn)
            
            # Check for nested transaction
            is_nested = state['active']
            
            if not is_nested:
                # Start new transaction
                conn.execute('BEGIN IMMEDIATE')
                state['active'] = True
                state['depth'] = 1
                state['start_time'] = datetime.now()
                self._register_transaction(conn_id)
                logger.debug(f"Transaction started{' - ' + name if name else ''}")
            else:
                # Create savepoint for nested transaction
                state['depth'] += 1
                savepoint_name = name or f"sp_{state['depth']}_{int(time.time()*1000)}"
                sp = Savepoint(savepoint_name, conn)
                state['savepoints'].append(sp)
                self._add_savepoint_to_transaction(conn_id, savepoint_name)
                logger.debug(f"Nested transaction (savepoint: {savepoint_name})")
            
            self.metrics.total_started += 1
            yield conn
            
            # Commit if outermost transaction
            if not is_nested:
                conn.execute('COMMIT')
                state['active'] = False
                state['depth'] = 0
                state['start_time'] = None
                self._unregister_transaction(conn_id)
                logger.debug("Transaction committed")
                self.metrics.total_committed += 1
            else:
                # Release savepoint for nested transaction
                if state['savepoints']:
                    sp = state['savepoints'].pop()
                    sp.release()
                    state['depth'] -= 1
                logger.debug("Nested transaction committed (savepoint released)")
                
        except Exception as e:
            # Rollback on error
            if conn:
                try:
                    if not state['active'] or state['depth'] == 1:
                        # Rollback entire transaction
                        conn.execute('ROLLBACK')
                        logger.warning(f"Transaction rolled back due to error: {e}")
                    elif state['savepoints']:
                        # Rollback to savepoint
                        sp = state['savepoints'].pop()
                        sp.rollback()
                        state['depth'] -= 1
                        logger.debug(f"Nested transaction rolled back to savepoint")
                    
                    state['active'] = False
                    state['depth'] = 0
                    state['start_time'] = None
                    if conn_id := id(conn):
                        self._unregister_transaction(conn_id)
                        
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {rollback_error}")
            
            self.metrics.total_rolled_back += 1
            raise
        
        finally:
            # Return connection to pool
            if conn and pooled:
                duration_ms = (time.time() - start_time) * 1000
                self.metrics.record_duration(duration_ms)
                self.pool.return_connection(pooled)
    
    def retry_on_failure(self, max_attempts: Optional[int] = None,
                         retryable_errors: Optional[tuple] = None):
        """
        Decorator for automatic retry on transient failures
        
        Args:
            max_attempts: Override default max retries
            retryable_errors: Custom tuple of retryable exceptions
            
        Example:
            @tm.retry_on_failure(max_attempts=5)
            def process_payment(payment_id):
                with tm.transaction() as conn:
                    # ... operations that might fail temporarily
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs) -> Any:
                attempts = max_attempts or self.max_retries
                errors = retryable_errors or self.TRANSIENT_ERRORS
                
                last_error = None
                
                for attempt in range(attempts):
                    try:
                        return func(*args, **kwargs)
                        
                    except errors as e:
                        last_error = e
                        
                        if attempt < attempts - 1:
                            self.metrics.total_retries += 1
                            
                            if self._is_deadlock(e):
                                self.metrics.deadlock_count += 1
                                logger.warning(f"Deadlock detected (attempt {attempt + 1}/{attempts})")
                            elif self._is_transient_error(e):
                                logger.warning(f"Transient error (attempt {attempt + 1}/{attempts}): {e}")
                            
                            # Calculate and apply delay
                            delay = self._calculate_delay(attempt)
                            logger.debug(f"Retrying in {delay:.2f}s")
                            time.sleep(delay)
                        else:
                            logger.error(f"All retry attempts exhausted after {attempts} tries")
                            self.metrics.total_rolled_back += 1
                            raise RetryExhaustedError(
                                f"Failed after {attempts} attempts. Last error: {e}"
                            ) from last_error
                
                # Should not reach here, but just in case
                raise last_error
            
            # Preserve function metadata
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        
        return decorator
    
    def execute_in_transaction(self, func: Callable[[sqlite3.Connection], Any],
                               max_retries: Optional[int] = None) -> Any:
        """
        Execute a function within a transaction with retry logic
        
        Args:
            func: Function that takes connection as argument
            max_retries: Override default max retries
            
        Returns:
            Result of the function
            
        Example:
            result = tm.execute_in_transaction(
                lambda conn: conn.execute('SELECT COUNT(*) FROM accounts').fetchone()[0]
            )
        """
        attempts = max_retries or self.max_retries
        last_error = None
        
        for attempt in range(attempts):
            try:
                with self.transaction() as conn:
                    return func(conn)
                    
            except Exception as e:
                last_error = e
                
                if attempt < attempts - 1 and self._is_transient_error(e):
                    self.metrics.total_retries += 1
                    delay = self._calculate_delay(attempt)
                    logger.warning(f"Retryable error (attempt {attempt + 1}/{attempts}): {e}")
                    time.sleep(delay)
                else:
                    raise
        
        raise RetryExhaustedError(
            f"Failed after {attempts} attempts. Last error: {last_error}"
        ) from last_error
    
    def get_active_transactions(self) -> List[Dict[str, Any]]:
        """
        Get list of currently active transactions
        
        Returns:
            List of transaction info dictionaries
        """
        with self._lock:
            result = []
            for conn_id, info in self._active_transactions.items():
                duration = (datetime.now() - info['start_time']).total_seconds()
                result.append({
                    'connection_id': conn_id,
                    'thread_id': info['thread_id'],
                    'start_time': info['start_time'].isoformat(),
                    'duration_seconds': round(duration, 2),
                    'savepoints': info['savepoints']
                })
            return result
    
    def detect_long_running_transactions(self, threshold_seconds: float = 60.0) -> List[Dict[str, Any]]:
        """
        Detect transactions running longer than threshold
        
        Args:
            threshold_seconds: Duration threshold in seconds
            
        Returns:
            List of long-running transaction info
        """
        all_transactions = self.get_active_transactions()
        return [t for t in all_transactions if t['duration_seconds'] > threshold_seconds]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get transaction metrics"""
        return {
            'metrics': self.metrics.to_dict(),
            'active_transactions': len(self._active_transactions),
            'config': {
                'max_retries': self.max_retries,
                'base_delay': self.base_delay,
                'max_delay': self.max_delay,
                'jitter_enabled': self.jitter
            }
        }
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics = TransactionMetrics()
        logger.info("Transaction metrics reset")


class BatchTransaction:
    """
    Execute multiple operations in a single transaction
    
    Useful for batch processing where all operations must succeed or fail together
    
    Usage:
        bt = BatchTransaction(tm)
        (bt
            .add_operation(lambda conn: insert_account(conn, acc1))
            .add_operation(lambda conn: insert_account(conn, acc2))
            .add_operation(lambda conn: update_balance(conn, id1, 1000))
            .execute())
    """
    
    def __init__(self, transaction_manager: TransactionManager):
        """
        Initialize batch transaction
        
        Args:
            transaction_manager: TransactionManager instance
        """
        self.tm = transaction_manager
        self.operations: List[Callable[[sqlite3.Connection], Any]] = []
    
    def add_operation(self, operation: Callable[[sqlite3.Connection], Any]) -> 'BatchTransaction':
        """
        Add an operation to the batch
        
        Args:
            operation: Function that takes connection and performs operation
            
        Returns:
            Self for chaining
        """
        self.operations.append(operation)
        return self
    
    def execute(self) -> List[Any]:
        """
        Execute all operations in a single transaction
        
        Returns:
            List of results from each operation
            
        Raises:
            Exception: If any operation fails, all are rolled back
        """
        if not self.operations:
            logger.warning("No operations to execute in batch transaction")
            return []
        
        results = []
        
        def batch_func(conn: sqlite3.Connection) -> List[Any]:
            for operation in self.operations:
                result = operation(conn)
                results.append(result)
            return results
        
        self.tm.execute_in_transaction(batch_func)
        return results
    
    def execute_with_retry(self, max_retries: Optional[int] = None) -> List[Any]:
        """
        Execute batch with retry logic
        
        Args:
            max_retries: Maximum retry attempts
            
        Returns:
            List of results from each operation
        """
        if not self.operations:
            return []
        
        results = []
        
        def batch_func(conn: sqlite3.Connection) -> List[Any]:
            for operation in self.operations:
                result = operation(conn)
                results.append(result)
            return results
        
        self.tm.execute_in_transaction(batch_func, max_retries=max_retries)
        return results
