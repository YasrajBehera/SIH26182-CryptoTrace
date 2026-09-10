# Attribution Scoring Method

> **IMPORTANT DISCLAIMER**: The attribution score is an analytical ranking heuristic.
> It is **NOT proof of wallet ownership** or VASP association. It is a probabilistic
> ranking based on synthetic data and heuristics, intended for investigative triage
> and prioritization only.

## Overview

The attribution engine assigns a score (0-100) and confidence level (HIGH/MEDIUM/LOW)
to each VASP candidate for a given wallet address. The score is a weighted combination
of five evidence components.

## Scoring Components

| Component | Default Weight | Description |
|-----------|---------------|-------------|
| Graph Proximity | 0.25 | How close the address is to known VASP addresses in the transaction graph |
| Known Address Match | 0.35 | Direct match against the VASP intelligence database |
| Temporal Consistency | 0.15 | Whether transaction timestamps match VASP operating patterns |
| Transaction Flow | 0.15 | Whether the flow pattern matches VASP behavior |
| Cluster Evidence | 0.10 | Whether the address shares a community cluster with known VASPs |

Weights are normalized so they sum to 1.0. All weights are configurable via `ScoringWeights`.

### 1. Graph Proximity (0.25)

Evaluates hop-distance from the target address to known VASP addresses:

- **Direct neighbor of known VASP**: 100 points
- **2 hops**: 60 points
- **3 hops**: 30 points
- **4 hops**: 10 points
- **Neighbors present but no VASP match**: 5 points
- **No path / no neighbors**: 0 points

### 2. Known Address Match (0.35)

Direct lookup in the VASP intelligence database:

- **Exact match (verified)**: confidence * 100 points (e.g., 0.95 -> 95)
- **Exact match (disputed)**: confidence * 100 points (e.g., 0.25 -> 25)
- **No match**: 0 points

This is the highest-weighted component because a direct database match is the
strongest available signal.

### 3. Temporal Consistency (0.15)

Measures regularity of transaction intervals (coefficient of variation):

- **CV < 0.3** (regular, exchange-like): 80 points
- **CV 0.3-0.7** (moderately regular): 60 points
- **CV 0.7-1.5** (variable): 40 points
- **CV > 1.5** (highly irregular): 15 points
- **Insufficient data**: 20 points

### 4. Transaction Flow (0.15)

Analyzes counterparty diversity and flow balance:

- **>20 unique counterparties**: 80 points (exchange-like)
- **10-20 counterparties**: 65 points (active wallet)
- **3-10 counterparties**: 40 points
- **<3 counterparties**: 15 points
- **Balanced in/out flow**: +10 bonus (capped at 100)

### 5. Cluster Evidence (0.10)

Checks if the address shares a community cluster (WCC/Louvain/Leiden) with known VASPs:

- **In cluster with known VASP(s)**: 50 + (25 * overlap_count) points
- **In cluster, no known VASP overlap**: 15 points
- **Not in any cluster**: 0 points

## Final Score Calculation

```
score = sum(component_score * component_weight) for all 5 components
score = clamp(score, 0, 100)
```

## Confidence Levels

| Level | Score Range |
|-------|-------------|
| HIGH | >= 70 |
| MEDIUM | 40 - 69 |
| LOW | < 40 |

## Determinism

The scoring is fully deterministic. Given the same inputs (address, chain, graph_data),
the engine produces identical scores, evidence, and rankings every time. There is
no randomness, no external API calls, and no machine learning inference.

## Evidence Provenance

Every evidence item stores:
- `evidence_id`: unique identifier
- `evidence_type`: which scoring component generated it
- `attribution_id`: links to the analysis
- `confidence`: sub-score for this component (0.0-1.0)
- `description`: human-readable explanation
- `provenance.created_at`: ISO timestamp
- `provenance.created_by`: always "attribution_engine"
- `provenance.method`: scoring method identifier
- `provenance.version`: engine version

## Limitations

1. **Synthetic data only**: The VASP database is hardcoded synthetic data.
   No real VASP ownership data is used.
2. **No ML/GNN**: Scoring is heuristic-based, not learned from data.
3. **No LLM attribution**: No language model is used for analysis.
4. **Chain coverage**: Only eth and bsc chains are covered.
5. **Static weights**: Default weights are not tuned against ground truth.
6. **No real-world validation**: Scoring thresholds are not calibrated
   against known real VASP associations.
7. **Graph-dependent**: Quality depends on graph data from Member 2.
   Empty/limited graph data produces low-confidence results.
8. **Not regulatory**: This is a research/investigation tool, not a
   regulatory compliance tool. Scores should not be used as sole
   evidence for any legal or compliance action.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/intelligence/address/{address} | VASP lookup for an address |
| GET | /api/v1/intelligence/vasp/names | List known VASP names |
| POST | /api/v1/attribution/analyze | Run attribution analysis |
| GET | /api/v1/attribution/weights | Get current scoring weights |
| GET | /api/v1/evidence/{evidence_id} | Get specific evidence record |
| GET | /api/v1/evidence/address/{address} | Get evidence for an address |
| GET | /api/v1/evidence/attribution/{attr_id} | Get evidence for an analysis |
