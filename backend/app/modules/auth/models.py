from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    owner = "owner"
    manager = "manager"
    staff = "staff"
