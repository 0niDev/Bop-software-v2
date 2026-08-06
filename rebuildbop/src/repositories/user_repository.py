"""
User Repository - Handles user authentication and management

Provides methods for user CRUD operations, authentication, and role-based access.
"""

from typing import Any, Dict, List, Optional
import bcrypt
from .base_repository import BaseRepository


class UserRepository(BaseRepository):
    """
    Repository for user-related database operations.
    
    Handles user authentication, password hashing, and role management.
    """
    
    def __init__(self):
        super().__init__('users', 'id')
    
    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user with username and password.
        
        Args:
            username: User's username
            password: User's plain text password
            
        Returns:
            User dictionary if authentication successful, None otherwise
        """
        query = "SELECT * FROM users WHERE username = ? OR email = ?"
        user = self.execute_single(query, (username, username))
        
        if not user:
            return None
        
        # Verify password hash
        stored_hash = user.get('password_hash') or user.get('password')
        if stored_hash and bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            # Remove password from returned data
            user.pop('password_hash', None)
            user.pop('password', None)
            return user
        
        return None
    
    def create_user(self, username: str, password: str, email: str, 
                    role: str = 'user', **kwargs) -> int:
        """
        Create a new user with hashed password.
        
        Args:
            username: User's username
            password: Plain text password (will be hashed)
            email: User's email address
            role: User role (default: 'user')
            **kwargs: Additional user fields
            
        Returns:
            ID of the newly created user
        """
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        columns = ['username', 'password_hash', 'email', 'role']
        values = [username, password_hash, email, role]
        
        # Add additional fields
        for key, value in kwargs.items():
            if key not in ['username', 'password', 'email', 'role']:
                columns.append(key)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        
        query = f"INSERT INTO users ({column_names}) VALUES ({placeholders})"
        return self.execute_insert(query, tuple(values))
    
    def update_password(self, user_id: int, new_password: str) -> bool:
        """
        Update a user's password.
        
        Args:
            user_id: User's ID
            new_password: New plain text password
            
        Returns:
            True if update was successful
        """
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        query = "UPDATE users SET password_hash = ? WHERE id = ?"
        rows_affected = self.execute_update(query, (password_hash, user_id))
        return rows_affected > 0
    
    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by username.
        
        Args:
            username: User's username
            
        Returns:
            User dictionary or None if not found
        """
        query = "SELECT * FROM users WHERE username = ?"
        user = self.execute_single(query, (username,))
        if user:
            user.pop('password_hash', None)
            user.pop('password', None)
        return user
    
    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by email.
        
        Args:
            email: User's email address
            
        Returns:
            User dictionary or None if not found
        """
        query = "SELECT * FROM users WHERE email = ?"
        user = self.execute_single(query, (email,))
        if user:
            user.pop('password_hash', None)
            user.pop('password', None)
        return user
    
    def get_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        """
        Get all users with a specific role.
        
        Args:
            role: Role name
            
        Returns:
            List of user dictionaries
        """
        query = "SELECT * FROM users WHERE role = ? ORDER BY username"
        users = self.execute_query(query, (role,))
        for user in users:
            user.pop('password_hash', None)
            user.pop('password', None)
        return users
    
    def get_all_active_users(self) -> List[Dict[str, Any]]:
        """
        Get all active users.
        
        Returns:
            List of active user dictionaries
        """
        query = "SELECT * FROM users WHERE is_active = 1 ORDER BY username"
        users = self.execute_query(query)
        for user in users:
            user.pop('password_hash', None)
            user.pop('password', None)
        return users
    
    def update_last_login(self, user_id: int) -> bool:
        """
        Update user's last login timestamp.
        
        Args:
            user_id: User's ID
            
        Returns:
            True if update was successful
        """
        from datetime import datetime
        query = "UPDATE users SET last_login = ? WHERE id = ?"
        now = datetime.now().isoformat()
        rows_affected = self.execute_update(query, (now, user_id))
        return rows_affected > 0
    
    def set_user_active(self, user_id: int, is_active: bool) -> bool:
        """
        Activate or deactivate a user.
        
        Args:
            user_id: User's ID
            is_active: Active status
            
        Returns:
            True if update was successful
        """
        query = "UPDATE users SET is_active = ? WHERE id = ?"
        rows_affected = self.execute_update(query, (1 if is_active else 0, user_id))
        return rows_affected > 0
    
    def check_username_exists(self, username: str) -> bool:
        """
        Check if a username already exists.
        
        Args:
            username: Username to check
            
        Returns:
            True if username exists, False otherwise
        """
        return self.exists("username = ?", (username,))
    
    def check_email_exists(self, email: str) -> bool:
        """
        Check if an email already exists.
        
        Args:
            email: Email to check
            
        Returns:
            True if email exists, False otherwise
        """
        return self.exists("email = ?", (email,))
    
    # Abstract method implementations
    def create(self, data: Dict[str, Any]) -> int:
        """Create a new user."""
        required_fields = ['username', 'password', 'email']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        return self.create_user(
            username=data['username'],
            password=data['password'],
            email=data['email'],
            role=data.get('role', 'user'),
            **{k: v for k, v in data.items() if k not in required_fields}
        )
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """Update an existing user."""
        if 'password' in data:
            # Handle password separately
            self.update_password(id_value, data.pop('password'))
        
        if not data:
            return True
        
        # Build update query
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        
        query = f"UPDATE users SET {set_clause} WHERE id = ?"
        values.append(id_value)
        
        rows_affected = self.execute_update(query, tuple(values))
        return rows_affected > 0
    
    def delete(self, id_value: Any) -> bool:
        """Soft delete a user by setting is_active to 0."""
        return self.set_user_active(id_value, False)
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        """Find users by arbitrary criteria."""
        if not kwargs:
            return self.get_all()
        
        conditions = []
        values = []
        
        for key, value in kwargs.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        
        where_clause = ' AND '.join(conditions)
        query = f"SELECT * FROM users WHERE {where_clause} ORDER BY username"
        
        users = self.execute_query(query, tuple(values))
        for user in users:
            user.pop('password_hash', None)
            user.pop('password', None)
        
        return users
