"""
Base Service - Abstract base class for all services

Provides common functionality and enforces service layer patterns.
All services should inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseService(ABC):
    """
    Abstract base class for all service classes.
    
    Provides common business logic operations and enforces
    consistent patterns across all services.
    
    Attributes:
        service_name (str): Name of the service for logging
    """
    
    def __init__(self, service_name: str = "BaseService"):
        """
        Initialize the base service.
        
        Args:
            service_name: Name identifier for logging purposes
        """
        self.service_name = service_name
        self._created_at = datetime.now()
    
    @abstractmethod
    def get_by_id(self, id_value: Any) -> Optional[Dict[str, Any]]:
        """
        Get a single record by ID.
        
        Args:
            id_value: The primary key value
            
        Returns:
            Dictionary representing the entity or None if not found
        """
        pass
    
    @abstractmethod
    def get_all(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get all records with optional filters.
        
        Args:
            filters: Optional dictionary of filter criteria
            
        Returns:
            List of dictionaries representing entities
        """
        pass
    
    @abstractmethod
    def create(self, data: Dict[str, Any]) -> int:
        """
        Create a new record.
        
        Args:
            data: Dictionary of field names and values
            
        Returns:
            ID of the newly created record
        """
        pass
    
    @abstractmethod
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """
        Update an existing record.
        
        Args:
            id_value: Primary key value
            data: Dictionary of field names and values to update
            
        Returns:
            True if update was successful
        """
        pass
    
    @abstractmethod
    def delete(self, id_value: Any) -> bool:
        """
        Delete a record.
        
        Args:
            id_value: Primary key value
            
        Returns:
            True if deletion was successful
        """
        pass
    
    def validate_data(self, data: Dict[str, Any], required_fields: List[str] = None) -> bool:
        """
        Validate data dictionary.
        
        Args:
            data: Data dictionary to validate
            required_fields: List of required field names
            
        Returns:
            True if validation passes
            
        Raises:
            ValueError: If validation fails
        """
        if required_fields:
            missing = [field for field in required_fields if field not in data]
            if missing:
                raise ValueError(f"Missing required fields: {', '.join(missing)}")
        return True
    
    def log_operation(self, operation: str, details: str = "") -> None:
        """
        Log a service operation.
        
        Args:
            operation: Operation name (CREATE, UPDATE, DELETE, etc.)
            details: Additional details about the operation
        """
        logger.info(f"[{self.service_name}] {operation}: {details}")
    
    def format_currency(self, amount: float, currency: str = "PKR") -> str:
        """
        Format amount as currency string.
        
        Args:
            amount: Numeric amount
            currency: Currency code/symbol
            
        Returns:
            Formatted currency string
        """
        return f"{currency} {amount:,.2f}"
    
    def parse_amount(self, value: Any) -> float:
        """
        Parse various input types to float amount.
        
        Args:
            value: Value to parse (string, int, float, Decimal)
            
        Returns:
            Float representation
        """
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove currency symbols and commas
            cleaned = value.replace(',', '').replace('$', '').replace('PKR', '').strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0


class ServiceError(Exception):
    """Custom exception for service layer errors."""
    pass


class ValidationError(ServiceError):
    """Exception raised when data validation fails."""
    pass


class NotFoundError(ServiceError):
    """Exception raised when a record is not found."""
    pass


class BusinessRuleError(ServiceError):
    """Exception raised when a business rule is violated."""
    pass
