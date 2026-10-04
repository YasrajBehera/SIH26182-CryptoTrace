from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from blockchain.chains import canonical_chain, normalize_address
from evidence.models import EvidenceType
from evidence.service import EvidenceService
from intelligence.models import VASPAddress
from intelligence.repository import VASPRepository


def observed_vasp_interactions(
    vasp_repo: VASPRepository,
    address: str,
    chain: str,
    graph_data: Optional[Dict] = None,
) -> List[Tuple[VASPAddress, Dict, str]]:
    """Transfers observed between ``address`` and a verified VASP address.

    Every entry is read straight out of ingested flow data, so a VASP address can
    only reach this list if the chain actually produced a transfer with it. The
    directory lookup is chain-scoped, so a verified address on one chain can never
    satisfy a match on another. Returns ``(directory_entry, flow, direction)``
    tuples, de-duplicated per transaction hash and direction so a duplicated flow
    cannot inflate an interaction count.
    """
    if not graph_data:
        return []

    canonical = canonical_chain(chain)
    known = {
        normalize_address(entry.address): entry
        for entry in vasp_repo.get_known_vasp_addresses(canonical)
    }
    if not known:
        return []

    wallet = f"{canonical}:{normalize_address(address)}"
    found: List[Tuple[VASPAddress, Dict, str]] = []
    seen = set()

    for flow in graph_data.get("flows") or []:
        src = (flow.get("source") or flow.get("sender") or "").strip()
        tgt = (flow.get("target") or flow.get("receiver") or "").strip()
        if src == wallet:
            counterpart, direction = tgt, "out"
        elif tgt == wallet:
            counterpart, direction = src, "in"
        else:
            continue
        entry = known.get(normalize_address(counterpart.split(":", 1)[-1]))
        if entry is None:
            continue
        key = ((flow.get("tx_hash") or "").strip(), direction, entry.address.lower())
        if key in seen:
            continue
        seen.add(key)
        found.append((entry, flow, direction))

    return found


# Strength of an *indirect* verified-address signal, scaled by how much real
# evidence supports it: more observed transfers with a verified address on the
# same chain means a stronger association. Every tier is capped below a direct
# directory hit, which is the strongest single piece of evidence available, so
# observed interaction can never outrank an actual directory match.
_VERIFIED_INTERACTION_TIERS = ((10, 60.0), (5, 45.0), (2, 30.0), (1, 15.0))


def _verified_interaction_score(count: int) -> float:
    for minimum, score in _VERIFIED_INTERACTION_TIERS:
        if count >= minimum:
            return score
    return 0.0


# The flow component answers a different question from the address component: not
# "is this a VASP address" but "does this wallet move value with one". It is
# therefore scaled separately, and a single observed transfer stays low here so
# that one incidental transfer can never on its own lift a wallet into MEDIUM.
_VERIFIED_FLOW_TIERS = ((10, 95.0), (5, 80.0), (2, 60.0), (1, 35.0))


def _verified_flow_score(count: int) -> float:
    for minimum, score in _VERIFIED_FLOW_TIERS:
        if count >= minimum:
            return score
    return 0.0


class ScoringWeights(BaseModel):
    graph_proximity: float = Field(0.25, ge=0.0, le=1.0)
    known_address_match: float = Field(0.35, ge=0.0, le=1.0)
    temporal_consistency: float = Field(0.15, ge=0.0, le=1.0)
    transaction_flow: float = Field(0.15, ge=0.0, le=1.0)
    cluster_evidence: float = Field(0.10, ge=0.0, le=1.0)

    def normalized(self) -> "ScoringWeights":
        total = (
            self.graph_proximity
            + self.known_address_match
            + self.temporal_consistency
            + self.transaction_flow
            + self.cluster_evidence
        )
        if total == 0:
            return ScoringWeights(
                graph_proximity=0.0,
                known_address_match=0.0,
                temporal_consistency=0.0,
                transaction_flow=0.0,
                cluster_evidence=0.0,
            )
        return ScoringWeights(
            graph_proximity=self.graph_proximity / total,
            known_address_match=self.known_address_match / total,
            temporal_consistency=self.temporal_consistency / total,
            transaction_flow=self.transaction_flow / total,
            cluster_evidence=self.cluster_evidence / total,
        )


class AttributionScorer:
    HIGH_THRESHOLD = 70.0
    MEDIUM_THRESHOLD = 40.0

    def __init__(
        self,
        vasp_repo: VASPRepository,
        evidence_svc: EvidenceService,
        weights: Optional[ScoringWeights] = None,
    ) -> None:
        self._vasp_repo = vasp_repo
        self._evidence_svc = evidence_svc
        self._weights = (weights or ScoringWeights()).normalized()

    @property
    def weights(self) -> ScoringWeights:
        return self._weights

    def score_graph_proximity(
        self,
        address: str,
        chain: str,
        neighbor_wallet_ids: List[str],
        path_data: Optional[Dict] = None,
    ) -> Tuple[float, List[str]]:
        known_vasps = self._vasp_repo.get_known_vasp_addresses(chain)
        known_wallet_ids = {
            f"{chain}:{a.address.lower()}" for a in known_vasps
        }
        known_addresses = {a.address.lower() for a in known_vasps}

        score = 0.0
        explanations: List[str] = []
        best_hops = float("inf")

        if path_data and path_data.get("found"):
            path = path_data.get("path", [])
            for i, node in enumerate(path):
                addr = node.split(":", 1)[-1].lower() if ":" in node else node.lower()
                if addr in known_addresses:
                    hops = i
                    if hops < best_hops:
                        best_hops = hops

        for nid in neighbor_wallet_ids:
            if nid in known_wallet_ids:
                score = max(score, 100.0)
                explanations.append(
                    f"Direct neighbor match with known VASP address"
                )

        if best_hops <= 4 and score < 100.0:
            hop_scores = {0: 100.0, 1: 80.0, 2: 60.0, 3: 30.0, 4: 10.0}
            score = max(score, hop_scores.get(best_hops, 5.0))
            explanations.append(
                f"Path to known VASP found in {best_hops} hops"
            )

        if score == 0.0 and neighbor_wallet_ids:
            score = 5.0
            explanations.append("Graph neighbors present but no VASP match")

        return min(score, 100.0), explanations

    def score_known_address_match(
        self,
        address: str,
        chain: str,
        graph_data: Optional[Dict] = None,
    ) -> Tuple[float, List[str]]:
        """Evidence that this wallet is, or provably transacts with, a VASP.

        Two kinds of real, chain-scoped evidence qualify, in strict precedence:

        1. The wallet *is* a verified directory address on this chain. Scored at
           the directory entry's own confidence.
        2. Transfers were actually observed between this wallet and a verified
           VASP address on this chain. Scored from the number of observed
           interactions, and always below a direct directory hit.

        Without the second case this component - the heaviest weight in the model
        - returned ``0.0`` for every wallet that is not itself a directory entry,
        which made the HIGH threshold unreachable no matter how much real
        exchange activity the chain produced. A repeated, on-chain, verifiable
        relationship with a verified VASP address is genuine address-match
        evidence and belongs in this component.
        """
        matches = self._vasp_repo.lookup_by_address(address, chain)
        if matches:
            best = max(matches, key=lambda m: m.confidence)
            score = best.confidence * 100.0
            explanations = [
                f"Direct match: {best.vasp_name} ({best.address_type.value}, "
                f"confidence={best.confidence:.2f})"
            ]
            return min(score, 100.0), explanations

        observed = observed_vasp_interactions(
            self._vasp_repo, address, chain, graph_data
        )
        if not observed:
            return 0.0, ["Address not found in VASP database"]

        names = sorted({entry.vasp_name for entry, _, _ in observed})
        score = _verified_interaction_score(len(observed))
        return score, [
            f"Not a directory address, but {len(observed)} transfer(s) observed "
            f"with verified {canonical_chain(chain)} address(es) of "
            f"{', '.join(names)}; indirect, so scored below a direct directory match"
        ]

    def score_temporal_consistency(
        self,
        address: str,
        chain: str,
        graph_data: Optional[Dict] = None,
    ) -> Tuple[float, List[str]]:
        if not graph_data:
            return 0.0, ["No graph data provided for temporal analysis"]

        flows = graph_data.get("flows", [])
        if not flows:
            edges = graph_data.get("edges", [])
            flows = edges

        if not flows:
            return 0.0, ["No transaction timestamps available"]

        timestamps = []
        for flow in flows:
            ts = flow.get("timestamp") or flow.get("block_timestamp")
            if ts:
                timestamps.append(int(ts))

        if len(timestamps) < 2:
            return 20.0, ["Insufficient timestamps for temporal analysis"]

        timestamps.sort()
        intervals = [
            timestamps[i + 1] - timestamps[i]
            for i in range(len(timestamps) - 1)
        ]

        mean_interval = sum(intervals) / len(intervals)
        variance = sum((iv - mean_interval) ** 2 for iv in intervals) / len(intervals)
        cv = (variance ** 0.5) / mean_interval if mean_interval > 0 else 0.0

        if cv < 0.3:
            score = 80.0
            explanation = "Regular transaction intervals (exchange-like pattern)"
        elif cv < 0.7:
            score = 60.0
            explanation = "Moderately regular intervals (active wallet pattern)"
        elif cv < 1.5:
            score = 40.0
            explanation = "Variable intervals (irregular usage pattern)"
        else:
            score = 15.0
            explanation = "Highly irregular intervals (potential mixer/evasion pattern)"

        return score, [explanation]

    def score_transaction_flow(
        self,
        address: str,
        chain: str,
        graph_data: Optional[Dict] = None,
    ) -> Tuple[float, List[str]]:
        if not graph_data:
            return 0.0, ["No graph data for transaction flow analysis"]

        neighbors = graph_data.get("neighbors", [])
        flows = graph_data.get("flows", [])

        in_count = 0
        out_count = 0
        unique_counterparties = set()
        total_amount_in = 0.0
        total_amount_out = 0.0

        for flow in flows:
            src = flow.get("source") or flow.get("sender", "")
            tgt = flow.get("target") or flow.get("receiver", "")
            amt = float(flow.get("amount", 0))
            wallet_id = f"{chain}:{address.lower()}"
            if tgt == wallet_id:
                in_count += 1
                unique_counterparties.add(src)
                total_amount_in += amt
            elif src == wallet_id:
                out_count += 1
                unique_counterparties.add(tgt)
                total_amount_out += amt

        unique_count = len(unique_counterparties) or len(neighbors)

        # No observed activity at all is NOT a weak exchange-like pattern, it is
        # the absence of evidence. Awarding a positive score here (as the
        # "few counterparties" tier used to) fabricated an attribution signal
        # for wallets whose live fetch returned nothing, which produced ranked
        # candidates and evidence records out of pure absence.
        if not flows and not neighbors:
            return 0.0, [
                "No transaction activity was observed for this address; "
                "flow-based scoring does not apply"
            ]

        score = 0.0
        explanations: List[str] = []

        if unique_count > 20:
            score = 80.0
            explanations.append(
                f"Many unique counterparties ({unique_count}) - exchange-like pattern"
            )
        elif unique_count > 10:
            score = 65.0
            explanations.append(
                f"Moderate counterparties ({unique_count}) - active wallet"
            )
        elif unique_count > 3:
            score = 40.0
            explanations.append(
                f"Limited counterparties ({unique_count})"
            )
        else:
            score = 15.0
            explanations.append(
                f"Few counterparties ({unique_count})"
            )

        if in_count > 0 and out_count > 0:
            ratio = min(in_count, out_count) / max(in_count, out_count)
            if ratio > 0.7:
                score = min(score + 10, 100.0)
                explanations.append("Balanced in/out flow (exchange-like)")

        # Counterparty *count* alone cannot distinguish an exchange relationship
        # from ordinary activity: a wallet with 50 unrelated counterparties scored
        # identically to one with 50 counterparties including a verified VASP.
        # When real transfers with a verified VASP address on this chain were
        # observed, they are scored directly and take precedence over the
        # aggregate count. With no VASP counterparty the aggregate tiers above are
        # returned unchanged.
        observed = observed_vasp_interactions(
            self._vasp_repo, address, chain, graph_data
        )
        if observed:
            names = sorted({entry.vasp_name for entry, _, _ in observed})
            vasp_score = _verified_flow_score(len(observed))
            score = min(max(score, vasp_score), 100.0)
            explanations.append(
                f"{len(observed)} transfer(s) observed with verified "
                f"{canonical_chain(chain)} address(es) of {', '.join(names)}"
            )

        if not explanations:
            explanations.append("Insufficient flow data for analysis")

        return min(score, 100.0), explanations

    def score_cluster_evidence(
        self,
        address: str,
        chain: str,
        graph_data: Optional[Dict] = None,
    ) -> Tuple[float, List[str]]:
        if not graph_data:
            return 0.0, ["No graph data for cluster analysis"]

        communities = graph_data.get("communities", [])
        known_vasps = self._vasp_repo.get_known_vasp_addresses(chain)
        known_wallet_ids = {
            f"{chain}:{a.address.lower()}" for a in known_vasps
        }
        target_wallet_id = f"{chain}:{address.lower()}"

        score = 0.0
        explanations: List[str] = []

        for community in communities:
            wallet_ids = {
                w.get("wallet_id", "") for w in community.get("wallets", [])
            }
            if target_wallet_id in wallet_ids:
                overlap = wallet_ids & known_wallet_ids
                if overlap:
                    score = min(100.0, 50.0 + len(overlap) * 25.0)
                    explanations.append(
                        f"Shares cluster with {len(overlap)} known VASP address(es)"
                    )
                else:
                    score = 15.0
                    explanations.append(
                        "In community cluster but no known VASP overlap"
                    )
                break

        if not explanations:
            explanations.append("No cluster data available or address not in any cluster")

        return min(score, 100.0), explanations
