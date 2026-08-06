"""
Repository Layer - Data Access Objects for BOP ERP

This module provides repository classes for all entities in the system.
Each repository handles CRUD operations and optimized queries for its entity type.
"""

from .base_repository import BaseRepository
from .user_repository import UserRepository
from .party_repository import PartyRepository
from .item_repository import ItemRepository
from .account_repository import AccountRepository
from .invoice_repository import InvoiceRepository
from .stock_repository import StockRepository
from .transaction_repository import TransactionRepository
from .bank_repository import BankRepository
from .other_repositories import (
    ReportRepository,
    SettingsRepository,
    AuditRepository,
    TaxRepository,
    UnitRepository,
    CategoryRepository,
    BatchRepository
)

__all__ = [
    'BaseRepository',
    'UserRepository',
    'PartyRepository',
    'ItemRepository',
    'AccountRepository',
    'InvoiceRepository',
    'StockRepository',
    'TransactionRepository',
    'BankRepository',
    'ReportRepository',
    'SettingsRepository',
    'AuditRepository',
    'TaxRepository',
    'UnitRepository',
    'CategoryRepository',
    'BatchRepository',
]
