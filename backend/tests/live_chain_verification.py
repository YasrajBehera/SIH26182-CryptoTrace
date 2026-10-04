"""Live end-to-end verification against real chains.

Runs the REAL pipeline (provider -> BlockchainTransfer -> graph -> VASP ->
attribution -> evidence) for several different wallets on each supported chain to
prove the implementation is wallet-independent and case-independent.

Not part of the hermetic test suite: it performs live network calls.
Run with:  python -m tests.live_chain_verification
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".env"))
except Exception:  # noqa: BLE001
    pass

from attribution.adapter import build_graph_data  # noqa: E402,F401
from attribution.scoring import AttributionScorer  # noqa: E402
from pipeline.models import MODE_LIVE, InvestigationRequest  # noqa: E402
from pipeline.service import InvestigationPipeline  # noqa: E402

# Different wallets per chain, none of them hardcoded into product logic.
WALLETS = [
    ("ronin", "0x3b3adf1422f84254b7fbb0e7ca62bd0865133fe3", "ronin-A (active)"),
    ("ronin", "0x854fbac43f70d16b5ac07dd1e79bd9026f94857c", "ronin-B (older activity)"),
    ("ronin", "0x59032868cf021f776cceb37604cfb2166a1e727b", "ronin-C (active)"),
    ("eth", "0x28C6c06298d514Db089934071355E5743bf21d60", "eth-A (Binance hot wallet)"),
    ("eth", "0x503828976D22510aad0201ac7EC88293211D23Da", "eth-B (Kraken)"),
]


def summarize(result) -> dict:
    top = result.candidates[0] if result.candidates else None
    return {
        "status": result.status,
        "provider": result.provider,
        "data_source": result.data_source,
        "transfers_ingested": result.transfers_ingested,
        "graph_nodes": result.graph_nodes,
        "graph_edges": result.graph_edges,
        "evidence_records": result.evidence_count,
        "candidate": top.vasp_name if top else None,
        "score": top.score if top else None,
        "confidence": str(top.confidence).replace("Confidence.", "") if top else None,
        "evidence_ids": len(top.evidence_ids) if top else 0,
        "breakdown": top.score_breakdown if top else None,
    }


def _fmt_breakdown(bd) -> str:
    if bd is None:
        return "-"
    parts = [
        f"graph={bd.graph_proximity:g}",
        f"known={bd.known_address_match:g}",
        f"temporal={bd.temporal_consistency:g}",
        f"flow={bd.transaction_flow:g}",
        f"cluster={bd.cluster_evidence:g}",
    ]
    return " ".join(parts)


async def main() -> None:
    pipeline = InvestigationPipeline(sync_to_neo4j=False)
    # Same reference directory the live pipeline scores against.
    scorer = AttributionScorer(
        vasp_repo=pipeline._intel.repository_for("live"),
        evidence_svc=pipeline._attr._evidence,
        weights=pipeline._attr._scorer.weights,
    )
    print(f"{'case':<28} {'status':<14} {'xfer':>5} {'node':>5} {'edge':>5} "
          f"{'evid':>5}  {'cand':<10} {'score':>6} {'conf':<6}")
    print("-" * 104)
    for chain, address, label in WALLETS:
        request = InvestigationRequest(address=address, chain=chain)
        try:
            result = await pipeline.arun(request, mode=MODE_LIVE)
        except Exception as exc:  # noqa: BLE001
            print(f"{label:<28} ERROR {type(exc).__name__}: {str(exc)[:60]}")
            continue
        s = summarize(result)
        print(f"{label:<28} {s['status']:<14} {s['transfers_ingested']:>5} "
              f"{s['graph_nodes']:>5} {s['graph_edges']:>5} {s['evidence_records']:>5}  "
              f"{str(s['candidate']):<10} {str(s['score']):>6} {str(s['confidence']):<6}")
        print(f"{'':28}   breakdown: {_fmt_breakdown(s['breakdown'])} "
              f"evidence_ids={s['evidence_ids']}")

        # Prove the REAL transfers reached the graph and that the behavioural
        # scorer actually sees those flows (independent of VASP candidates).
        if result.transfers_ingested:
            graph = pipeline._transfers_to_graph(result.transactions, address)
            graph_data = pipeline._graph_to_graph_data(graph, address, chain)
            flows = graph_data.get("flows") or []
            flow_score, flow_why = scorer.score_transaction_flow(
                address, chain, graph_data
            )
            print(f"{'':28}   real flows={len(flows)} "
                  f"behavioural flow score={flow_score:g} :: {flow_why[:80]}")
        for note in result.limitations[:2]:
            print(f"{'':28}   ! {note[:150]}")


if __name__ == "__main__":
    asyncio.run(main())