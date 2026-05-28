"""User roles for RBAC."""

from enum import Enum


class UserRole(str, Enum):
    FOUNDER = "founder"
    ADMIN = "admin"
    REVIEWER = "reviewer"
    OPERATOR = "operator"
    READONLY = "readonly"


ROLE_HIERARCHY = {
    UserRole.READONLY: 0,
    UserRole.OPERATOR: 1,
    UserRole.REVIEWER: 2,
    UserRole.ADMIN: 3,
    UserRole.FOUNDER: 4,
}
