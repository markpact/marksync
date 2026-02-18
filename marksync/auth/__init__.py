"""
marksync.auth — JWT-based authentication and role-based access control.

Usage:
    from marksync.auth import require_role, get_current_user
    from marksync.auth.tokens import create_token, verify_token
    from marksync.auth.middleware import AuthMiddleware
    from marksync.auth.roles import Role, PERMISSIONS
"""

from marksync.auth.tokens import create_token, verify_token, TokenPayload
from marksync.auth.roles import Role, PERMISSIONS, has_permission
from marksync.auth.middleware import AuthMiddleware, get_current_user, require_role

__all__ = [
    "create_token",
    "verify_token",
    "TokenPayload",
    "Role",
    "PERMISSIONS",
    "has_permission",
    "AuthMiddleware",
    "get_current_user",
    "require_role",
]
