"""
Application configuration for BOP Pharmaceutical ERP System.

This module provides centralized configuration management using environment variables.
Supports SQLite Cloud as primary database with local SQLite fallback.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# Base directories
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
DATA_DIR: Path = BASE_DIR / "data"
LOG_DIR: Path = BASE_DIR / "logs"
BACKUP_DIR: Path = BASE_DIR / "backups"

for _dir in (DATA_DIR, LOG_DIR, BACKUP_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class DatabaseConfig:
    """
    Database connection configuration.
    
    Primary: SQLite Cloud (multi-user network database)
    Fallback: Local SQLite file
    """
    engine: str = field(default_factory=lambda: os.getenv("ERP_DB_ENGINE", "sqlitecloud"))
    
    # SQLite Cloud (Primary - Network)
    sqlite_cloud_url: str = field(
        default_factory=lambda: os.getenv("SQLITE_CLOUD_URL", "")
    )
    sqlite_cloud_api_key: str = field(
        default_factory=lambda: os.getenv("SQLITE_CLOUD_API_KEY", "")
    )
    sqlite_cloud_host: str = field(
        default_factory=lambda: os.getenv("SQLITE_CLOUD_HOST", "")
    )
    sqlite_cloud_port: int = field(
        default_factory=lambda: int(os.getenv("SQLITE_CLOUD_PORT", "8860"))
    )
    sqlite_cloud_database: str = field(
        default_factory=lambda: os.getenv("SQLITE_CLOUD_DATABASE", "")
    )
    
    # SQLite (Local Fallback)
    sqlite_path: str = field(
        default_factory=lambda: os.getenv("ERP_DB_PATH", str(DATA_DIR / "erp.db"))
    )
    
    # Connection Pool Settings
    pool_min_size: int = field(default_factory=lambda: int(os.getenv("DB_POOL_MIN", "10")))
    pool_max_size: int = field(default_factory=lambda: int(os.getenv("DB_POOL_MAX", "50")))
    
    foreign_keys: bool = True


@dataclass(frozen=True)
class LoggingConfig:
    level: str = field(default_factory=lambda: os.getenv("ERP_LOG_LEVEL", "INFO"))
    log_file: str = field(default_factory=lambda: str(LOG_DIR / "erp.log"))
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 5
    fmt: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


@dataclass(frozen=True)
class BackupConfig:
    backup_dir: str = field(default_factory=lambda: str(BACKUP_DIR))
    auto_backup_enabled: bool = True
    auto_backup_interval_hours: int = 24
    keep_last_n_backups: int = 14


@dataclass(frozen=True)
class AppConfig:
    app_name: str = "BOP Pharmaceutical ERP"
    app_version: str = "2.0.0"
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    default_currency: str = "PKR"
    date_format: str = "yyyy-MM-dd"


# Singleton accessor
_config: AppConfig | None = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def set_sqlite_cloud_api_key(api_key: str) -> None:
    """Set SQLite Cloud API key at runtime."""
    global _config
    if _config is not None:
        object.__setattr__(_config.database, 'sqlite_cloud_api_key', api_key)
    os.environ["SQLITE_CLOUD_API_KEY"] = api_key
