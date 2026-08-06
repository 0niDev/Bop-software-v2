"""Tests for MigrationManager."""
import pytest
import sqlite3
from pathlib import Path
from src.database.migration_manager import MigrationManager
from src.database.migrations import V1_0_initial_schema


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
