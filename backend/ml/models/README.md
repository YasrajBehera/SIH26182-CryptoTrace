
# CryptoTrace ML Deployment Package

This package contains the trained suspicious-wallet risk classifier.

## Files

- cryptotrace_elliptic2_lightgbm.joblib
  Trained LightGBM model.

- metadata.json
  Model version, dataset provenance, features, threshold and metrics.

- MODEL_CARD.md
  Model limitations, intended use and safety information.

- SHA256SUMS.json
  Integrity checksums.

## Training Dataset

Elliptic2

Blockchain:
Bitcoin

Labels:
- licit
- suspicious

## Important Domain Limitation

This model was trained using Bitcoin-focused Elliptic2 data.

It must NOT automatically be represented as a validated Ethereum
or multi-chain suspicious-wallet classifier.

## CryptoTrace Live Inference Rule

Do not train or fine-tune the model using the investigation target wallet.

Do not fabricate missing live features.

If required features are unavailable or incompatible:

UNKNOWN / NOT ASSESSED

must be returned.

## Risk Separation

ML suspicious-wallet probability is separate from:

- VASP attribution score
- sanctions intelligence
- graph evidence
- transaction evidence

The ML probability is an analytical risk signal and does not establish
criminality or ownership.

## Recommended Backend Integration

Load the model once when the FastAPI application starts.

For each eligible wallet:

1. Obtain real blockchain-derived features.
2. Validate the feature schema.
3. Run model.predict_proba().
4. Return the probability.
5. Attach model version and dataset version to evidence.
6. If required features are missing, return UNKNOWN.

Never substitute synthetic values for missing live features.
