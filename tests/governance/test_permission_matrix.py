import pytest

from core.permissions import Permission
from core.rbac import can_approve_level, role_has_permission
from core.roles import UserRole


def test_readonly_cannot_prepare():
    assert not role_has_permission(UserRole.READONLY, Permission.ACTION_PREPARE)


def test_operator_can_prepare_not_level_3():
    assert role_has_permission(UserRole.OPERATOR, Permission.ACTION_PREPARE)
    assert not can_approve_level(UserRole.OPERATOR, 3)


def test_founder_can_approve_level_4():
    assert can_approve_level(UserRole.FOUNDER, 4)
