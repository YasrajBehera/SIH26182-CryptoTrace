"""Provider interface for multi-chain blockchain ingestion.

The rest of CryptoTrace (graph, intelligence, attribution, evidence, reports)
only ever consumes :class:`~blockchain.models.BlockchainTransfer`. It must never
import a vendor SDK, a chain-specific request shape, or a provider-specific raw
object. Everything chain-specific lives behind :class:`BlockchainProvider`.

Data-source honesty (non-negotiable)
------------------------------------
A provider returns a :class:`ProviderResult` that states *exactly* where the
data came from and what it does not cover. There is deliberately no
``get_transfers_or_demo`` style method anywhere in this module: a provider that
cannot obtain real data raises, so a live investigation can never be silently
served synthetic transactions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from blockchain.chains import ChainSpec, resolve_chain
from blockchain.models import BlockchainTransfer

#: Data-source vocabulary shared by the backend and the UI.
SOURCE_LIVE = "live"
SOURCE_DEMO = "demo"

#: Status vocabulary. ``LIVE_PARTIAL`` means real chain data that is known to be
#: incomplete (e.g. discovered through a bounded scan) - never synthetic data.
STATUS_LIVE = "LIVE"
STATUS_LIVE_PARTIAL = "LIVE_PARTIAL"
#: A real provider answered and genuinely found nothing. Not an error.
STATUS_NO_DATA = "NO_DATA"
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
STATUS_UNAVAILABLE = "LIVE_DATA_UNAVAILABLE"

#: Every status a :class:`ProviderResult` is allowed to report.
STATUSES = frozenset(
    {
        STATUS_LIVE,
        STATUS_LIVE_PARTIAL,
        STATUS_NO_DATA,
        STATUS_NOT_CONFIGURED,
        STATUS_UNAVAILABLE,
    }
)


@dataclass
class ProviderResult:
    """Normalized transfers plus honest provenance metadata."""

    chain: str
    address: str
    #: ``live`` only for real chain data, ``demo`` only for synthetic data.
    data_source: str
    #: One of the ``STATUS_*`` constants above.
    status: str
    #: Provider/transport label surfaced to the UI, e.g. ``alchemy``,
    #: ``ronin-rpc``. Never used to imply a data source it does not represent.
    provider: str
    transfers: List[BlockchainTransfer] = field(default_factory=list)
    #: True when the provider knowingly returned an incomplete view.
    truncated: bool = False
    #: Human-readable statements about what this result does and does not cover.
    limitations: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Guard the honesty contract at its boundary: a result must always say
        # where it came from and how complete it is, so no downstream layer has
        # to guess whether an empty status means "live and empty" or "unknown".
        if self.data_source not in (SOURCE_LIVE, SOURCE_DEMO):
            raise ValueError(
                f"data_source must be {SOURCE_LIVE!r} or {SOURCE_DEMO!r}, "
                f"got {self.data_source!r}"
            )
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}, got {self.status!r}")

    @property
    def is_live(self) -> bool:
        return self.data_source == SOURCE_LIVE

    @property
    def count(self) -> int:
        return len(self.transfers)


class BlockchainProvider(ABC):
    """A source of normalized transfers for exactly one chain."""

    #: Canonical chain id this provider serves, e.g. ``"eth"``.
    chain_name: str = ""
    #: Short label for provenance/UI, e.g. ``"alchemy"``.
    provider_name: str = ""
    #: Set to ``False`` when the provider is compiled in but cannot serve data
    #: without configuration. Registry selection raises
    #: ``ProviderNotConfiguredError`` rather than returning empty results.
    available: bool = True

    @property
    def spec(self) -> ChainSpec:
        return resolve_chain(self.chain_name)

    @abstractmethod
    async def get_transfers(
        self,
        address: str,
        limit: Optional[int] = None,
    ) -> ProviderResult:
        """Fetch real transfers for ``address`` on this provider's chain.

        Implementations must raise
        :class:`~blockchain.errors.LiveDataUnavailableError` (or a subclass) when
        real data cannot be obtained, and must never substitute synthetic data.
        """

    async def is_healthy(self) -> bool:
        """Cheap liveness probe. ``False`` never raises."""
        try:
            await self.get_transfers(
                address="0x0000000000000000000000000000000000000001", limit=1
            )
        except Exception:  # noqa: BLE001 - health probes must never raise
            return False
        return True

    async def aclose(self) -> None:
        """Release any pooled HTTP resources."""
        return None