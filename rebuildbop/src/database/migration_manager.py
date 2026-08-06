"""
Database Migration System

Provides schema migration with:
- Version tracking
- Rollback support
- Data migration
- Verification tests

Migration files naming: V{version}_{description}.py
Example: V1_0_initial_schema.py, V1_1_add_tax_columns.py
"""

import sqlite3
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import importlib.util

logger = logging.getLogger(__name__)


@dataclass
class Migration:
    """Represents a database migration"""
    version: int
    description: str
    up_script: str
    down_script: Optional[str]
    created_at: datetime
    executed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'description': self.description,
            'up_script': self.up_script,
            'down_script': self.down_script,
            'created_at': self.created_at.isoformat(),
            'executed_at': self.executed_at.isoformat() if self.executed_at else None
        }


class MigrationManager:
    """
    Manage database schema migrations
    
    Features:
    - Automatic version tracking
    - Rollback to any version
    - Data migration support
    - Pre/post migration hooks
    - Verification tests
    
    Usage:
        mm = MigrationManager(pool)
        
        # Run all pending migrations
        mm.migrate()
        
        # Rollback to specific version
        mm.rollback(target_version=5)
        
        # Get current version
        current = mm.get_current_version()
    """
    
    def __init__(self, connection_pool: Any):
        """
        Initialize migration manager
        
        Args:
            connection_pool: Connection pool instance
        """
        self.pool = connection_pool
        self.migrations_dir = Path(__file__).parent / 'migrations'
        self._migrations: List[Migration] = []
        self._ensure_version_table()
    
    def _ensure_version_table(self):
        """Create migration version tracking table if not exists"""
        with self.pool.get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS _schema_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version INTEGER UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT,
                    execution_time_ms INTEGER
                )
            ''')
            conn.commit()
            logger.debug("Schema versions table ensured")
    
    def _load_migrations_from_files(self):
        """Load migration scripts from files"""
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")
            return
        
        migration_files = sorted(self.migrations_dir.glob('V*.py'))
        
        for file_path in migration_files:
            try:
                # Parse version from filename (e.g., V1_0_initial_schema.py)
                filename = file_path.stem
                parts = filename.split('_', 1)
                if len(parts) < 2 or not parts[0].startswith('V'):
                    logger.warning(f"Invalid migration filename: {filename}")
                    continue
                
                version_str = parts[0][1:]  # Remove 'V' prefix
                version = int(version_str.replace('_', ''))
                description = parts[1]
                
                # Load module
                spec = importlib.util.spec_from_file_location(filename, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Get migration scripts
                up_script = getattr(module, 'UP', '')
                down_script = getattr(module, 'DOWN', None)
                
                migration = Migration(
                    version=version,
                    description=description,
                    up_script=up_script,
                    down_script=down_script,
                    created_at=datetime.fromtimestamp(file_path.stat().st_mtime)
                )
                self._migrations.append(migration)
                
                logger.debug(f"Loaded migration V{version}: {description}")
                
            except Exception as e:
                logger.error(f"Failed to load migration {file_path}: {e}")
        
        # Sort by version
        self._migrations.sort(key=lambda m: m.version)
    
    def get_current_version(self) -> int:
        """Get current database schema version"""
        with self.pool.get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(version) FROM _schema_versions')
            result = cursor.fetchone()[0]
            return result if result is not None else 0
    
    def get_applied_migrations(self) -> List[Dict[str, Any]]:
        """Get list of applied migrations"""
        with self.pool.get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT version, description, applied_at, checksum, execution_time_ms
                FROM _schema_versions
                ORDER BY version
            ''')
            
            return [
                {
                    'version': row['version'],
                    'description': row['description'],
                    'applied_at': row['applied_at'],
                    'checksum': row['checksum'],
                    'execution_time_ms': row['execution_time_ms']
                }
                for row in cursor.fetchall()
            ]
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get list of migrations not yet applied"""
        self._load_migrations_from_files()
        applied_versions = {m['version'] for m in self.get_applied_migrations()}
        return [m for m in self._migrations if m.version not in applied_versions]
    
    def migrate(self, target_version: Optional[int] = None) -> bool:
        """
        Apply all pending migrations up to target version
        
        Args:
            target_version: Target version (None for latest)
            
        Returns:
            True if migrations were applied
        """
        self._load_migrations_from_files()
        pending = self.get_pending_migrations()
        
        if not pending:
            logger.info("Database is up to date")
            return False
        
        current_version = self.get_current_version()
        target = target_version or (pending[-1].version if pending else current_version)
        
        logger.info(f"Migrating from version {current_version} to {target}")
        
        with self.pool.get_connection_context() as conn:
            cursor = conn.cursor()
            
            for migration in pending:
                if migration.version > target:
                    break
                
                logger.info(f"Applying migration V{migration.version}: {migration.description}")
                
                try:
                    start_time = datetime.now()
                    
                    # Execute migration script
                    for statement in migration.up_script.split(';'):
                        statement = statement.strip()
                        if statement:
                            cursor.execute(statement)
                    
                    # Calculate checksum
                    checksum = self._calculate_checksum(migration.up_script)
                    
                    # Record migration
                    execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                    cursor.execute('''
                        INSERT INTO _schema_versions (version, description, checksum, execution_time_ms)
                        VALUES (?, ?, ?, ?)
                    ''', (migration.version, migration.description, checksum, execution_time))
                    
                    conn.commit()
                    migration.executed_at = datetime.now()
                    
                    logger.info(f"Migration V{migration.version} applied in {execution_time}ms")
                    
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Migration V{migration.version} failed: {e}")
                    raise
        
        logger.info(f"Migration complete. Current version: {target}")
        return True
    
    def rollback(self, target_version: int = 0) -> bool:
        """
        Rollback database to target version
        
        Args:
            target_version: Version to rollback to
            
        Returns:
            True if rollback was performed
        """
        applied = self.get_applied_migrations()
        
        if not applied:
            logger.info("No migrations to rollback")
            return False
        
        # Get migrations to rollback (in reverse order)
        to_rollback = [m for m in reversed(applied) if m['version'] > target_version]
        
        if not to_rollback:
            logger.info(f"Already at or below version {target_version}")
            return False
        
        logger.info(f"Rolling back {len(to_rollback)} migrations to version {target_version}")
        
        # Reload migrations to get DOWN scripts
        self._load_migrations_from_files()
        migration_map = {m.version: m for m in self._migrations}
        
        with self.pool.get_connection_context() as conn:
            cursor = conn.cursor()
            
            for migration_info in to_rollback:
                version = migration_info['version']
                migration = migration_map.get(version)
                
                if not migration:
                    logger.error(f"Cannot find migration V{version} for rollback")
                    continue
                
                if not migration.down_script:
                    logger.warning(f"No rollback script for V{version}, skipping")
                    continue
                
                logger.info(f"Rolling back V{version}: {migration.description}")
                
                try:
                    # Execute rollback script
                    for statement in migration.down_script.split(';'):
                        statement = statement.strip()
                        if statement:
                            cursor.execute(statement)
                    
                    # Remove from version tracking
                    cursor.execute('DELETE FROM _schema_versions WHERE version = ?', (version,))
                    conn.commit()
                    
                    logger.info(f"Rollback V{version} complete")
                    
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Rollback V{version} failed: {e}")
                    raise
        
        logger.info(f"Rollback complete. Current version: {target_version}")
        return True
    
    def _calculate_checksum(self, script: str) -> str:
        """Calculate MD5 checksum of migration script"""
        import hashlib
        return hashlib.md5(script.encode()).hexdigest()
    
    def verify_migrations(self) -> Dict[str, Any]:
        """
        Verify migration integrity
        
        Returns:
            Verification results
        """
        results = {
            'success': True,
            'issues': [],
            'current_version': self.get_current_version(),
            'total_migrations': len(self._migrations),
            'applied_count': 0,
            'pending_count': 0
        }
        
        applied = self.get_applied_migrations()
        results['applied_count'] = len(applied)
        
        self._load_migrations_from_files()
        pending = self.get_pending_migrations()
        results['pending_count'] = len(pending)
        
        # Check for missing migrations in sequence
        versions = sorted([m.version for m in self._migrations])
        for i, version in enumerate(versions):
            expected = i + 1
            if version != expected:
                results['issues'].append(f"Gap in version sequence: expected {expected}, found {version}")
                results['success'] = False
        
        # Check for applied migrations without files
        applied_versions = {m['version'] for m in applied}
        file_versions = {m.version for m in self._migrations}
        missing_files = applied_versions - file_versions
        if missing_files:
            results['issues'].append(f"Applied migrations with missing files: {missing_files}")
            results['success'] = False
        
        # Verify checksums
        for applied_m in applied:
            migration = next((m for m in self._migrations if m.version == applied_m['version']), None)
            if migration:
                expected_checksum = self._calculate_checksum(migration.up_script)
                if applied_m.get('checksum') != expected_checksum:
                    results['issues'].append(f"Checksum mismatch for V{applied_m['version']}")
                    results['success'] = False
        
        return results
    
    def add_migration(self, description: str, version: Optional[int] = None) -> Path:
        """
        Create a new migration file template
        
        Args:
            description: Migration description
            version: Optional version number (auto-increments if not provided)
            
        Returns:
            Path to created migration file
        """
        if version is None:
            version = self.get_current_version() + 1
        
        # Format version string (e.g., V1_0, V2_5)
        major = version // 10
        minor = version % 10
        version_str = f"V{major}_{minor}"
        
        # Create filename
        filename = f"{version_str}_{description.lower().replace(' ', '_')}.py"
        file_path = self.migrations_dir / filename
        
        # Ensure directory exists
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        
        # Write template
        template = f'''"""
Migration V{version}: {description}

Created: {datetime.now().isoformat()}
"""

UP = """
-- Add your UP migration SQL here
-- Example: ALTER TABLE accounts ADD COLUMN new_column TEXT;
"""

DOWN = """
-- Add your DOWN migration SQL here (optional)
-- Example: ALTER TABLE accounts DROP COLUMN new_column;
"""

def pre_migrate(conn):
    """Optional: Code to run before migration"""
    pass

def post_migrate(conn):
    """Optional: Code to run after migration"""
    pass
'''
        
        file_path.write_text(template)
        logger.info(f"Created migration template: {file_path}")
        
        return file_path


# Convenience functions for common migrations
COMMON_MIGRATIONS = {
    'add_timestamps': '''
        ALTER TABLE {table} ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        ALTER TABLE {table} ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    ''',
    
    'add_soft_delete': '''
        ALTER TABLE {table} ADD COLUMN deleted_at TIMESTAMP NULL;
        ALTER TABLE {table} ADD COLUMN is_active INTEGER DEFAULT 1;
    ''',
    
    'add_audit_fields': '''
        ALTER TABLE {table} ADD COLUMN created_by INTEGER;
        ALTER TABLE {table} ADD COLUMN updated_by INTEGER;
    ''',
    
    'create_index': 'CREATE INDEX IF NOT EXISTS idx_{table}_{column} ON {table}({column});',
    
    'create_unique_index': 'CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_{column}_unique ON {table}({column});'
}


def generate_index_migration(table: str, columns: list[str],
                             description: str = "") -> str:
    """
    Generate migration script for creating indexes
    
    Args:
        table: Table name
        columns: List of column names
        description: Optional description
        
    Returns:
        Migration script content string
    """
    up_statements = []
    down_statements = []
    
    for col in columns:
        idx_name = f"idx_{table}_{col}"
        up_statements.append(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({col});")
        down_statements.append(f"DROP INDEX IF EXISTS {idx_name};")
    
    up_script = '\n'.join(up_statements)
    down_script = '\n'.join(down_statements)
    
    return 'UP = """\n' + up_script + '\n"""\n\nDOWN = """\n' + down_script + '\n"""'
