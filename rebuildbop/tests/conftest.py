"""
Test Configuration and Fixtures for BOP ERP System
==================================================
Provides pytest configuration, fixtures, and utilities for all test phases.
"""
import os
import sys
import pytest
from pathlib import Path
from typing import Generator, Optional
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Test database configuration
TEST_DB_CONFIG = {
    'host': os.getenv('SQLITE_CLOUD_HOST', 'localhost'),
    'port': int(os.getenv('SQLITE_CLOUD_PORT', '8443')),
    'username': os.getenv('SQLITE_CLOUD_USERNAME', 'test_user'),
    'password': os.getenv('SQLITE_CLOUD_PASSWORD', 'test_pass'),
    'database': os.getenv('SQLITE_CLOUD_DATABASE', 'bop_test'),
    'use_ssl': False,
}

# Local SQLite fallback for offline testing
TEST_LOCAL_DB_PATH = Path(__file__).parent / 'test_bop_local.db'


@pytest.fixture(scope='session')
def test_db_config() -> dict:
    """Provide test database configuration."""
    return TEST_DB_CONFIG


@pytest.fixture(scope='session')
def local_db_path() -> Path:
    """Provide path to local test database."""
    return TEST_LOCAL_DB_PATH


@pytest.fixture
def cleanup_db(local_db_path: Path) -> Generator[None, None, None]:
    """Clean up test database before and after tests."""
    # Cleanup before
    if local_db_path.exists():
        local_db_path.unlink()
    
    yield
    
    # Cleanup after
    if local_db_path.exists():
        local_db_path.unlink()


@pytest.fixture
def sample_account_data() -> dict:
    """Sample account data for testing."""
    return {
        'code': '1001',
        'name': 'Test Cash Account',
        'account_type': 'ASSET',
        'parent_id': None,
        'description': 'Test account for unit tests',
        'is_active': True,
    }


@pytest.fixture
def sample_party_data() -> dict:
    """Sample party data for testing."""
    return {
        'code': 'P001',
        'name': 'Test Customer Ltd',
        'party_type': 'CUSTOMER',
        'email': 'test@example.com',
        'phone': '+1234567890',
        'address': '123 Test Street',
        'city': 'Test City',
        'country': 'Test Country',
        'is_active': True,
    }


@pytest.fixture
def sample_item_data() -> dict:
    """Sample item data for testing."""
    return {
        'code': 'ITEM001',
        'name': 'Test Product',
        'item_type': 'FINISHED_GOOD',
        'unit_of_measure': 'PCS',
        'standard_cost': 10.00,
        'selling_price': 15.00,
        'reorder_level': 10,
        'is_active': True,
    }


@pytest.fixture
def sample_journal_entry_data() -> dict:
    """Sample journal entry data for testing."""
    return {
        'date': '2024-01-15',
        'description': 'Test journal entry',
        'reference': 'TEST-JE-001',
        'entries': [
            {
                'account_code': '1001',
                'debit': 1000.00,
                'credit': 0.00,
            },
            {
                'account_code': '2001',
                'debit': 0.00,
                'credit': 1000.00,
            }
        ]
    }


@pytest.fixture
def sample_invoice_data() -> dict:
    """Sample sales invoice data for testing."""
    return {
        'invoice_number': 'INV-2024-001',
        'date': '2024-01-15',
        'party_code': 'P001',
        'due_date': '2024-02-15',
        'status': 'DRAFT',
        'line_items': [
            {
                'item_code': 'ITEM001',
                'quantity': 10,
                'unit_price': 15.00,
                'discount_percent': 0,
            },
            {
                'item_code': 'ITEM002',
                'quantity': 5,
                'unit_price': 20.00,
                'discount_percent': 10,
            }
        ]
    }


def pytest_addoption(parser):
    """Add custom command-line options to pytest."""
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="run slow tests"
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers",
        "performance: marks tests as performance benchmarks"
    )
    config.addinivalue_line(
        "markers",
        "database: marks tests that require database connection"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    # Skip slow tests by default unless explicitly requested
    if not config.getoption("--runslow"):
        skip_slow = pytest.mark.skip(reason="need --runslow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
