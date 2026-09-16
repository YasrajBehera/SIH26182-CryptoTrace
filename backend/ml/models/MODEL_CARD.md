
# CryptoTrace Suspicious Wallet Risk Classifier

## Model

- Version: 1.0.0
- Algorithm: LightGBM
- Task: Binary classification
- Positive class: suspicious
- Negative class: licit

## Dataset

- Dataset: Elliptic2
- Source: Kaggle — ellipticco/elliptic2-data-set
- License: CC BY-NC-ND 4.0
- Blockchain represented by training data: Bitcoin
- Labels: connected-component labels from connected_components.csv

## Label Mapping

- licit = 0
- suspicious = 1

## Features

- outgoing_count
- incoming_count
- tx_count
- unique_counterparties

## Data Split

- Training: 70%
- Validation: 15%
- Test: 15%
- Stratified split
- Random state: 42

## Class Imbalance

Training scale_pos_weight:

41.4739

## Decision Threshold

Threshold:

0.0500

The threshold was selected using the validation set only.
The test set was not used for threshold selection.

## Final Test Metrics

| Metric | Result |
|---|---:|
| Precision | 0.0237 |
| Recall | 0.9924 |
| F1 | 0.0463 |
| ROC-AUC | 0.5276 |
| PR-AUC | 0.0251 |

## Confusion Matrix

[[  900 64209]
 [   12  1558]]

## Intended Use

This model provides a machine-learning risk signal for
blockchain investigation workflows.

It is NOT proof that a wallet belongs to a criminal,
criminal organization, or illicit entity.

The ML probability must remain separate from:

1. VASP attribution score
2. Sanctions/intelligence evidence
3. Transaction graph evidence

## Live Inference Safety

The target wallet must never be added to the training dataset.

Live inference must use observed blockchain-derived features.

Synthetic values must not be substituted for missing features.

If required features are unavailable or incompatible with the
training schema, the system must return UNKNOWN / NOT ASSESSED.

## Domain Limitation

Elliptic2 is Bitcoin-focused training data.

The model must not automatically be presented as validated
for Ethereum, Tron, BNB Chain, Solana, Polygon, or other chains.

Cross-chain deployment requires feature/schema compatibility
and appropriate validation.

## Versioning

Model version: 1.0.0

Dataset: Elliptic2

Created: 2026-09-15T07:06:19.315760+00:00
