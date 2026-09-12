"""Wallet summary services built on the (memory|postgres) wallet repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from wallets.models import WalletSummaryOut
from wallets.repository import WalletRepository, make_wallet_repository


def _iso(ts) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


class WalletService:
    def __init__(self, repository: Optional[WalletRepository] = None) -> None:
        self._repo = repository or make_wallet_repository()

    @property
    def repository(self) -> WalletRepository:
        return self._repo

    def register_analysis(
        self,
        address: str,
        chain: str,
        transfers: List[Dict],
        risk: str = "unknown",
        risk_score: Optional[int] = None,
        investigation_status: str = "analyzed",
    ) -> Dict:
        """Persist an analysis'' transfers and derive the wallet summary."""
        self._repo.store_transactions(list(transfers))
        volumes = self._repo.coin_volumes(address, chain)
        summary = {
            "address": address.lower(),
            "chain": chain,
            "first_seen": volumes.get("first_seen"),
            "last_activity": volumes.get("last_activity"),
            "transaction_count": volumes.get("count", 0),
            "incoming_volume": str(volumes.get("incoming", 0)),
            "outgoing_volume": str(volumes.get("outgoing", 0)),
            "risk": risk,
            "risk_score": risk_score,
            "investigation_status": investigation_status,
        }
        return self._repo.upsert_summary(summary)

    def summarize(self, address: str, chain: str) -> Optional[WalletSummaryOut]:
        volumes = self._repo.coin_volumes(address, chain)
        stored = self._repo.get_summary(address, chain)
        if volumes["count"] == 0 and stored is None:
            return None
        sources_name = type(self._repo).__name__
        return WalletSummaryOut(
            address=address.lower(),
            network=chain,
            first_seen=_iso(
                (stored or {}).get("first_seen", volumes.get("first_seen"))
            ),
            last_activity=_iso(
                (stored or {}).get("last_activity", volumes.get("last_activity"))
            ),
            transaction_count=volumes["count"],
            incoming_volume=str(volumes.get("incoming", 0)),
            outgoing_volume=str(volumes.get("outgoing", 0)),
            balance=(stored or {}).get("balance"),
            risk=(stored or {}).get("risk", "unknown"),
            risk_score=(stored or {}).get("risk_score"),
            investigation_status=(stored or {}).get(
                "investigation_status", "not_analyzed"
            ),
            source="postgres" if sources_name == "DbWalletRepository" else "memory",
        )