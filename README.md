<div align="center">

# 🛡️ CryptoTrace

### 🔗 Automated Attribution of Unknown Cryptocurrency Wallets to Nearest VASPs

**Smart India Hackathon 2026 · Problem Statement SIH26182**

**Ministry of Home Affairs (MHA) · Blockchain & Cybersecurity**

<br>

**Multi-Chain Blockchain Intelligence · VASP Attribution · Transaction Graph Analysis · Explainable Evidence**

</div>

---

## 🔗 All Important Links

| 🚀 Resource | 🔗 Link | 📌 Description |
|---|---|---|
| 🌐 **Live CryptoTrace Platform** | **[Open Live Application](YOUR_NETLIFY_FRONTEND_URL)** | Investigator dashboard for wallet analysis, attribution, graph exploration and evidence |
| ⚙️ **Live Backend API** | **[Render Backend](https://sih26182-cryptotrace.onrender.com)** | Production FastAPI backend powering CryptoTrace |
| 💻 **GitHub Repository** | **[SIH26182-CryptoTrace](https://github.com/YasrajBehera/SIH26182-CryptoTrace)** | Complete frontend, backend, blockchain providers, attribution engine and tests |
| 🤖 **AI-Narrated Project Demo** | **[Watch on YouTube](https://youtu.be/xp3hxlscSh4)** | Full narrated overview of CryptoTrace, its architecture, workflow and capabilities |
| 🔎 **Ronin Investigation — 6 min** | **[Watch on YouTube](https://youtu.be/SRiYH3l_j14?si=OeOd8XtfT7QKN1rf)** | Focused Ronin investigation covering provider architecture, transaction graph, VASP attribution and explainable investigation results |

---

## 🎥 Featured Demonstrations

### 🔎 Ronin Wallet Investigation — 6 Minute Technical Demo

▶️ **[Watch the Ronin Investigation on YouTube](https://youtu.be/SRiYH3l_j14?si=OeOd8XtfT7QKN1rf)**

This focused demonstration shows how **CryptoTrace investigates a Ronin wallet** and converts blockchain activity into an explainable VASP-attribution result.

It demonstrates:

- 🔗 **Ronin blockchain provider integration**
- 🔍 Wallet-level transaction investigation
- 🕸️ Transaction graph construction
- 🏦 Chain-aware VASP intelligence
- 🎯 VASP relationship scoring
- 📊 Multi-component attribution scoring
- 🧾 Evidence-backed explanations
- 🔎 Matched VASP address visibility
- 🧬 Transaction-hash traceability
- ⚠️ Coverage and provider limitations
- 🚦 `HIGH / MEDIUM / LOW / UNKNOWN` attribution classification
- 🛡️ Separation between investigative association and proof of wallet ownership

> **Important:** This single 6-minute video is both the **Ronin Investigation Demo** and the **criminal-wallet investigation explanation**. It demonstrates the investigation workflow and attribution methodology; CryptoTrace does not claim that an attribution score alone proves criminality or wallet ownership.

---

### 🤖 Full AI-Narrated CryptoTrace Demo

▶️ **[Watch the Full Project Demo](https://youtu.be/xp3hxlscSh4)**

A broader walkthrough covering the CryptoTrace platform, investigation workflow, architecture and major project capabilities.

---

## 🚨 The Problem

Cryptocurrency investigations often begin with only one piece of information:

```text
Unknown / Suspicious Wallet Address
                ↓
              ???
                ↓
       Which VASP is related?
```

Investigators may need to manually inspect large numbers of transactions, counterparties and blockchain records before identifying a possible relationship with a **Virtual Asset Service Provider (VASP)**.

**CryptoTrace automates this investigation pipeline.**

```text
Unknown Wallet
      ↓
Blockchain Provider
      ↓
Transaction Ingestion
      ↓
Transaction Graph
      ↓
Graph & Flow Analysis
      ↓
VASP Intelligence
      ↓
Attribution Engine
      ↓
Evidence & Explainability
      ↓
Ranked VASP Candidates
```

The objective is not to declare who owns a wallet.

The objective is to provide investigators with **ranked, explainable VASP relationships backed by observable evidence** that can support further investigation and lawful requests for information.

---

## 🧠 What is CryptoTrace?

**CryptoTrace** is a blockchain-intelligence and VASP-attribution platform developed for:

> **SIH26182 — Automated Attribution of Unknown Cryptocurrency Wallets to Nearest Virtual Asset Service Providers (VASPs) through Blockchain Intelligence APIs**

The platform combines:

`Blockchain Data` → `Graph Analysis` → `VASP Intelligence` → `Attribution Scoring` → `Evidence`

to help investigators understand how an unknown cryptocurrency wallet is connected to known VASP infrastructure.

---

## ✨ Core Capabilities

| Capability | Implementation |
|---|---|
| 🔗 **Blockchain Intelligence** | Provider-based blockchain transaction ingestion |
| 🦊 **Ethereum Support** | Alchemy-backed Ethereum transaction retrieval |
| 🟣 **Ronin Support** | Ronin Mainnet provider architecture with official JSON-RPC and optional Alchemy support |
| 🕸️ **Transaction Graph** | Directed wallet-to-wallet transaction graph construction |
| 🔍 **Graph Investigation** | BFS, DFS, shortest-path and transaction-flow analysis |
| 🏦 **VASP Intelligence** | Chain-scoped curated VASP address intelligence |
| 🎯 **Attribution Engine** | Multi-signal deterministic VASP scoring |
| 🔁 **VASP Interaction Analysis** | Repeated observed interactions with verified VASP addresses |
| ⏱️ **Temporal Analysis** | Transaction-pattern and temporal-consistency signals |
| 🧾 **Evidence Traceability** | Matched addresses, transaction hashes, source references and limitations |
| 🤖 **ML Signal** | Auxiliary suspicious-wallet probability signal |
| 📊 **Investigator Dashboard** | React + TypeScript investigation interface |
| 📄 **Reporting** | Investigation/report generation |
| 🔐 **Security** | JWT authentication and role-based access controls |
| 🧪 **Testing** | Extensive backend and frontend automated test suites |

---

# 🟣 Ronin Mainnet Integration

One of the major additions to CryptoTrace is a dedicated **Ronin investigation path**.

Instead of treating every EVM-compatible network as Ethereum, CryptoTrace uses a provider architecture that keeps blockchain identity and provenance chain-specific.

```text
Investigation Request
        │
        ├── chain = ethereum
        │       ↓
        │   Ethereum Provider
        │       ↓
        │     Alchemy
        │
        └── chain = ronin
                ↓
           Ronin Provider
            ↙       ↘
   Official RPC    Alchemy*
```

`*` Alchemy Ronin access depends on Ronin Mainnet being enabled for the configured API key.

### Ronin Provider Features

The Ronin implementation includes:

- Ronin-specific provider routing
- Official Ronin JSON-RPC support
- Optional Alchemy Ronin support
- Chain-qualified wallet identity
- Provider provenance
- Configurable bounded scanning
- Native RON transaction handling
- Token-transfer investigation
- Provider rate-limit/error handling
- Explicit partial-coverage reporting

When the official public RPC cannot provide complete historical coverage, CryptoTrace does **not** silently claim that the wallet has no activity.

Instead, the investigation can be classified as:

```text
LIVE_PARTIAL
```

This communicates that real blockchain data was queried but the available coverage was incomplete.

---

# 🏦 Chain-Aware VASP Attribution

VASP attribution is **chain scoped**.

CryptoTrace does not assume that the same hexadecimal address represents the same intelligence entity across every blockchain.

Conceptually:

```text
ronin:0xABC...
```

and

```text
ethereum:0xABC...
```

are treated as separate chain-qualified identities for attribution purposes.

This prevents a Ronin VASP label from incorrectly influencing an Ethereum investigation.

---

## 🔎 Verified Ronin VASP Intelligence

The Ronin investigation path includes a curated public VASP reference for **Bitget**.

Verified Ronin address:

```text
0x5bdf85216ec1e38D6458C870992A69e38e03F7Ef
```

The reference is used as chain-scoped VASP intelligence for demonstrating and validating CryptoTrace's attribution pipeline.

A publicly observable Ronin transaction associated with this reference is also retained for provenance and verification.

```text
Transaction:
0x733fc397a5a565a5f4ee16f15f420640a1a77982a87f12145634abf3e41ca8b2

Block:
61,673,529

Value:
≈ 2770.21 RON
```

> The public transaction above supports verification of the referenced VASP address/activity. It does **not**, by itself, establish that every investigated wallet interacted with Bitget.

---

# 🎯 Explainable Attribution Engine

CryptoTrace does not return a VASP name from a single opaque rule.

The attribution engine evaluates multiple independent signals.

```text
                    ┌─────────────────────┐
                    │ Investigation Graph │
                    └──────────┬──────────┘
                               ↓
        ┌────────────────────────────────────────┐
        │       Attribution Signal Engine        │
        └────────────────────────────────────────┘
             ↓          ↓          ↓         ↓
          Graph      Known      Temporal    Flow
        Proximity    Address   Consistency Analysis
             └──────────┬──────────┬─────────┘
                        ↓
                Weighted Scoring
                        ↓
                Confidence Result
                        ↓
           HIGH / MEDIUM / LOW / UNKNOWN
```

The current scoring components include:

- **Graph proximity**
- **Known-address match**
- **Temporal consistency**
- **Transaction-flow evidence**
- **Cluster evidence**

A result must be supported by relevant evidence.

A high score should not exist simply because a VASP name appears in a directory.

---

# 🔁 Repeated VASP Interaction Evidence

CryptoTrace can analyze repeated observed interactions between an investigated wallet and a verified VASP address.

The engine considers factors such as:

```text
Wallet
  │
  ├──── Transaction 1 ────► VASP
  ├──── Transaction 2 ────► VASP
  ├──── Transaction 3 ────► VASP
  │
  └──── Repeated interaction pattern
                    ↓
             Attribution Signals
                    ↓
            Explainable Evidence
```

This allows stronger observed relationships to contribute more meaningfully than a single incidental interaction.

Importantly, the project does **not** lower the `HIGH` threshold simply to force a desired result.

---

# 🧾 Evidence & Explainability

Every meaningful attribution result should answer:

```text
WHO?
Which VASP candidate was identified?

WHY?
Which scoring components contributed?

WHERE?
Which blockchain and address were involved?

HOW?
Which transactions or graph relationships support it?

LIMITATIONS?
What data or provider limitations affect the conclusion?
```

Evidence can include:

- Matched VASP address
- Blockchain/network
- Transaction hash
- Direction of interaction
- Graph relationship
- Attribution component scores
- Intelligence source
- Provider provenance
- Coverage limitations

This makes the result easier for an investigator to inspect instead of presenting only a black-box percentage.

---

# 🚦 Honest Data Status

CryptoTrace explicitly distinguishes the source and completeness of investigation data.

| Status | Meaning |
|---|---|
| 🟢 **LIVE / REAL** | Data returned from a reachable live blockchain/provider path |
| 🟡 **LIVE_PARTIAL** | Real blockchain data was queried, but coverage is knowingly incomplete |
| 🔵 **NO_DATA** | Provider responded but no activity was found within the actual scanned range |
| 🧪 **DEMO / SYNTHETIC** | Controlled or generated data used for demonstration/testing |
| ⚙️ **NOT CONFIGURED** | Required provider or service configuration is unavailable |
| 🔴 **UNAVAILABLE / ERROR** | Provider or engine exists but could not complete the request |

### Why this matters

`NO_DATA` must never be interpreted automatically as:

```text
"This wallet has never transacted."
```

It means only that no matching activity was found **within the coverage actually searched**.

Likewise, controlled demo transactions remain **demo data** even when they are evaluated against a real curated VASP reference.

---

# 🧪 Controlled Ronin Attribution Demo

For demonstration and scoring validation, CryptoTrace contains a controlled Ronin investigation path that can exercise:

```text
Target Wallet
      ↕
Controlled Transaction Flows
      ↕
Verified Public VASP Reference
      ↓
Graph Analysis
      ↓
Attribution Engine
      ↓
Explainable Result
```

The generated transaction flows used by this controlled path are **synthetic/demo investigation data**.

The referenced Bitget Ronin address comes from the project's **curated public VASP intelligence**.

This separation is intentional:

```text
Controlled transaction flow ≠ claimed live transaction history

Verified VASP reference ≠ proof of investigated-wallet ownership
```

The controlled path exists to demonstrate how the production attribution engine behaves when meaningful VASP interaction evidence is available.

---

# 🏗️ System Architecture

```text
┌───────────────────────────────────────────────────────┐
│                Investigator Interface                 │
│           React + TypeScript + Tailwind               │
└────────────────────────┬──────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────┐
│                    FastAPI Backend                    │
│                                                       │
│   Authentication │ Investigation │ Reports │ API      │
└────────────────────────┬──────────────────────────────┘
                         │
          ┌──────────────┼───────────────┐
          ▼              ▼               ▼
┌────────────────┐ ┌──────────────┐ ┌─────────────────┐
│ Blockchain     │ │ Graph Engine │ │ VASP            │
│ Providers      │ │              │ │ Intelligence    │
│                │ │ NetworkX /   │ │                 │
│ Ethereum       │ │ Neo4j        │ │ Curated Public  │
│ Ronin          │ │              │ │ Intelligence    │
└───────┬────────┘ └──────┬───────┘ └────────┬────────┘
        │                 │                   │
        └─────────────────┼───────────────────┘
                          ▼
                ┌───────────────────┐
                │ Attribution       │
                │ Engine            │
                │                   │
                │ Graph             │
                │ Known Address     │
                │ Temporal          │
                │ Flow              │
                │ Cluster           │
                └─────────┬─────────┘
                          ▼
                ┌───────────────────┐
                │ Evidence &        │
                │ Explainability    │
                └─────────┬─────────┘
                          ▼
                ┌───────────────────┐
                │ Ranked VASP       │
                │ Candidates        │
                └───────────────────┘
```

---

# 🛠️ Technology Stack

### Frontend

```text
React
TypeScript
Vite
Tailwind CSS
```

### Backend

```text
Python
FastAPI
Pydantic
```

### Blockchain

```text
Alchemy
Ethereum
Ronin Mainnet
Ronin JSON-RPC
```

### Graph Intelligence

```text
NetworkX
Neo4j
BFS / DFS
Flow Analysis
```

### Machine Learning

```text
scikit-learn
LightGBM
Elliptic2-derived auxiliary signal
```

### Infrastructure

```text
Netlify — Frontend
Render  — Backend
GitHub  — Source Control
```

---

# 🧪 Testing & Validation

CryptoTrace has been developed with automated backend and frontend validation.

### Backend

```text
807 tests passed
```

Coverage includes:

- Attribution scoring
- Chain-scoped VASP matching
- Ronin provider behavior
- Real-data pipeline behavior
- Graph construction
- Pipeline integration
- Evidence generation
- Direct VASP matches
- Repeated VASP interactions
- Weak/incidental interactions
- Cross-chain isolation
- Error and partial-data handling

### Frontend

```text
146 tests passed
```

Additional checks:

```text
✓ TypeScript typecheck
✓ ESLint
✓ Production Vite build
```

---

# 📂 Project Structure

```text
SIH26182-CryptoTrace/
│
├── backend/
│   ├── app/
│   ├── attribution/
│   ├── blockchain/
│   │   ├── alchemy_client.py
│   │   ├── chains.py
│   │   ├── ethereum_provider.py
│   │   ├── ronin_provider.py
│   │   ├── providers.py
│   │   └── registry.py
│   │
│   ├── evidence/
│   ├── graph/
│   ├── intelligence/
│   ├── pipeline/
│   └── tests/
│
├── frontend/
│   └── src/
│
├── docs/
│
├── .env.example
└── README.md
```

---

# ⚙️ Environment Configuration

Example blockchain configuration:

```env
ALCHEMY_API_KEY=

RONIN_RPC_ENABLED=true
RONIN_RPC_URL=
RONIN_SCAN_BLOCKS=
RONIN_MAX_REQUESTS=
RONIN_NATIVE_SCAN_BLOCKS=
RONIN_RPC_CONCURRENCY=
RONIN_CHAIN_ID=
RONIN_ALCHEMY_API_KEY=
```

> Never commit real API keys, secrets or production credentials to GitHub.

---

# 🌐 Deployment

CryptoTrace uses a separated frontend/backend production architecture.

```text
GitHub main
     │
     ├──────────────► Netlify
     │                 │
     │                 └── React Frontend
     │
     └──────────────► Render
                       │
                       └── FastAPI Backend
```

The frontend communicates with the deployed backend using:

```env
VITE_API_BASE_URL=https://sih26182-cryptotrace.onrender.com
```

---

# ⚖️ Investigation & Attribution Disclaimer

CryptoTrace is an **investigative decision-support system**.

An attribution result indicates an observed or inferred relationship supported by the available blockchain graph, transaction-flow evidence and VASP intelligence.

It does **not** independently establish:

- Legal ownership of a cryptocurrency wallet
- The real-world identity of the wallet operator
- Criminal liability
- That every transfer involving a VASP address represents a custodial relationship
- That absence of activity in a bounded scan means the wallet has no historical activity

Final ownership or identity confirmation requires additional evidence such as verified VASP records, KYC information and appropriate investigative/legal procedures.

---

## 🏆 Smart India Hackathon 2026

| Field | Details |
|---|---|
| **Problem Statement ID** | `SIH26182` |
| **Organization** | Ministry of Home Affairs |
| **Category** | Software |
| **Theme** | Blockchain & Cybersecurity |
| **Project** | CryptoTrace |
| **Objective** | Automated attribution of unknown cryptocurrency wallets to nearest VASPs through blockchain intelligence |

---

<div align="center">

## 🛡️ CryptoTrace

### From an unknown wallet to explainable blockchain intelligence.

**Blockchain Intelligence · Graph Analysis · VASP Attribution · Evidence**

<br>

🎥 **[Full AI-Narrated Demo](https://youtu.be/xp3hxlscSh4)**  
🔎 **[6-Minute Ronin Investigation](https://youtu.be/SRiYH3l_j14?si=OeOd8XtfT7QKN1rf)**  
💻 **[GitHub Repository](https://github.com/YasrajBehera/SIH26182-CryptoTrace)**  
⚙️ **[Live Backend](https://sih26182-cryptotrace.onrender.com)**

<br>

**Built for Smart India Hackathon 2026 — SIH26182**

⭐ **If you find CryptoTrace useful, consider starring the repository.**

</div>
