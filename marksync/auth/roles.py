"""
marksync.auth.roles — Role definitions and permission matrix.

Roles:
    admin   — full access (deploy, approve, create, view)
    agent   — can create contracts and run pipelines, cannot approve
    viewer  — read-only access
"""

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    AGENT = "agent"
    VIEWER = "viewer"


PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {"view", "create", "edit", "deploy", "approve", "rollback", "manage_tokens"},
    Role.AGENT: {"view", "create", "edit", "deploy"},
    Role.VIEWER: {"view"},
}


def has_permission(role: Role | str, action: str) -> bool:
    """Return True if the given role is allowed to perform action."""
    try:
        r = Role(role)
    except ValueError:
        return False
    return action in PERMISSIONS.get(r, set())


def role_from_str(value: str) -> Role:
    """Parse a role string, defaulting to viewer on unknown values."""
    try:
        return Role(value.lower())
    except ValueError:
        return Role.VIEWER
