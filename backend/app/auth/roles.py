"""Role definitions for CryptoTrace.

THE BACKEND IS THE AUTHORIZATION AUTHORITY. The frontend permission grid in
``frontend/src/mock/users.ts`` is a UI convenience only; these maps are what
actually gates every protected endpoint via ``require_permission``.
"""

from __future__ import annotations

from typing import Dict, FrozenSet

# Roles that may be assigned to accounts. The first five are the seeded demo
# scaffolding; "read_only" is retained as a legacy role.
ROLES: FrozenSet[str] = frozenset(
    {"admin", "senior_investigator", "investigator", "analyst", "reviewer", "read_only"}
)

ROLE_PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "admin": frozenset(
        {
            "investigation.read",
            "investigation.create",
            "investigation.update",
            "wallet.read",
            "wallet.analyze",
            "graph.read",
            "attribution.read",
            "evidence.read",
            "evidence.create",
            "evidence.delete",
            "risk.read",
            "report.create",
            "report.export",
            "audit.read",
            "user.manage",
            "settings.manage",
            "search.read",
        }
    ),
    "senior_investigator": frozenset(
        {
            "investigation.read",
            "investigation.create",
            "investigation.update",
            "wallet.read",
            "wallet.analyze",
            "graph.read",
            "attribution.read",
            "evidence.read",
            "evidence.create",
            "evidence.delete",
            "risk.read",
            "report.create",
            "report.export",
            "search.read",
        }
    ),
    "investigator": frozenset(
        {
            "investigation.read",
            "investigation.create",
            "investigation.update",
            "wallet.read",
            "wallet.analyze",
            "graph.read",
            "attribution.read",
            "evidence.read",
            "evidence.create",
            "risk.read",
            "report.create",
            "report.export",
            "search.read",
        }
    ),
    "analyst": frozenset(
        {
            "investigation.read",
            "investigation.update",
            "wallet.read",
            "wallet.analyze",
            "graph.read",
            "attribution.read",
            "evidence.read",
            "evidence.create",
            "risk.read",
            "report.create",
            "search.read",
        }
    ),
    "reviewer": frozenset(
        {
            "investigation.read",
            "wallet.read",
            "graph.read",
            "attribution.read",
            "evidence.read",
            "risk.read",
            "report.create",
            "report.export",
            "search.read",
        }
    ),
    "read_only": frozenset(
        {
            "investigation.read",
            "wallet.read",
            "graph.read",
            "attribution.read",
            "evidence.read",
            "risk.read",
            "search.read",
        }
    ),
}


def role_has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())