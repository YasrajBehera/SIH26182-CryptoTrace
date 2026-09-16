"""Model card generator.

Builds a human-readable model card from a trained artifact's metadata so the
deployment can always answer *which* dataset/version/distribution it was
trained on, how it was evaluated, and exactly what it does NOT claim.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict


def build_model_card(metadata: Dict) -> str:
    data = metadata["dataset"]
    feat = metadata["features"]
    model = metadata["model"]
    metrics = metadata["metrics"]

    lines = [
        "# Model card: suspicious-wallet activity classifier",
        "",
        f"- Model version: ``{metadata.get('model_version')}``",
        f"- Training dataset version: ``{metadata.get('dataset_version')}``",
        f"- Generated: {metadata.get('created_at', '')}",
        "",
        "## What this model estimates",
        "",
        "Model-estimated suspicious activity probability for a wallet given its "
        "observable transaction history. It is an investigative signal only and "
        "is NOT a determination of criminality, illegality, or ownership. It is "
        "kept entirely separate from the VASP attribution score and the "
        "criminal/sanctions intelligence block.",
        "",
        f"## Dataset ({data.get('name')})",
        "",
        f"- GitHub: {data.get('source_github')}",
        f"- Kaggle: {data.get('source_kaggle')}",
        f"- License: {data.get('license')}",
        f"- Chain: {data.get('chain')}",
        f"- Labels: {data.get('labels')}",
        "",
        "Recorded directly from the loaded release files (never assumed):",
        "",
        f"- Wallets used for training: {data.get('n_wallets')}",
        f"- Illicit: {data.get('n_illicit')} ({data.get('illicit_ratio', 0):.1%})",
        f"- Licit: {data.get('n_licit')}",
        f"- Excluded (unknown label): {data.get('n_excluded_unknown_label')}",
        f"- Excluded (features not fully computable): "
        f"{data.get('n_excluded_missing_features')}",
        f"- Edges loaded: {data.get('edges_loaded')}",
        f"- File manifest (sha256):",
    ]
    for role, info in (data.get("files") or {}).items():
        lines.append(
            f"  - {role}: {info.get('basename')} ({info.get('rows')} rows, "
            f"sha256 {info.get('sha256', 'n/a')[:16]}…)"
        )

    lines += [
        "",
        "## Split methodology",
        "",
        "The labelled wallets are split with stratification into train / "
        "validation / test:",
        "",
        f"- Train: {data.get('train_rows')} wallets",
        f"- Validation: {data.get('validation_rows')} wallets "
        f"({data.get('validation_fraction', 0):.0%})",
        f"- Test: {data.get('test_rows')} wallets "
        f"({data.get('test_fraction', 0):.0%})",
        f"- Seed: {data.get('seed')}",
        "",
        "Early stopping AND the decision threshold are both selected on the "
        "validation split. The test split is untouched until the final, single "
        "evaluation pass — the threshold is never optimized, fitted, or tuned "
        "on the test set. The live target wallet is never part of any training "
        "window and no test label flows into any feature.",
        "",
        "## Features",
        "",
        f"- Number of features used: {feat.get('total')} (schema v{feat.get('schema_version')})",
    ]
    lines += [f"- {f}" for f in feat.get("required") or []]
    lines += [
        "",
        "All values are computed from real on-chain data with the same live "
        "feature extractor. A feature that cannot be computed for a wallet is "
        "UNAVAILABLE and forces UNKNOWN / NOT ASSESSED rather than an imputed "
        "value.",
        "",
        "## Model & training",
        "",
        f"- Algorithm: {model.get('algorithm')}",
        f"- Objective: {model.get('objective')}",
        f"- Eval metric: {model.get('eval_metric')}",
        f"- Class balance: scale_pos_weight={model.get('scale_pos_weight')}",
        f"- Decision threshold (selected ON VALIDATION): {model.get('threshold')}",
        "",
        "## Evaluation (held-out test set, evaluated once after threshold "
        "selection)",
        "",
        "| Metric | Value |",
        "|--|--|",
        f"| Precision | {metrics.get('precision', 0):.4f} |",
        f"| Recall | {metrics.get('recall', 0):.4f} |",
        f"| F1 | {metrics.get('f1', 0):.4f} |",
        f"| ROC-AUC | {metrics.get('roc_auc', 0):.4f} |",
        f"| PR-AUC | {metrics.get('pr_auc', 0):.4f} |",
        "",
        "Confusion matrix (test, at the validation-selected decision threshold):",
        "",
        "```",
        _format_confusion(metrics.get("confusion_matrix")),
        "```",
        "",
        "## Top contributing features",
        "",
    ]
    lines.extend(
        f"{i + 1}. ``{imp['feature']}`` (gain {imp['gain']:.3f})"
        for i, imp in enumerate(model.get("top_features") or [])
    )
    lines += [
        "",
        "## Known limitations",
        "",
        "- Features are computed from the observable transaction set actually "
        "held for the wallet; a wallet with too little history is UNKNOWN.",
        "- The signal does not prove criminality and must be corroborated.",
        "- Live inference never substitutes synthetic values for missing "
        "required features.",
    ]
    return "\n".join(lines)


def _format_confusion(cm) -> str:
    try:
        tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
    except Exception:
        return "unavailable"
    return (
        f"                   predicted licit   predicted illicit\n"
        f"actual licit        {tn:>5}              {fp:>5}\n"
        f"actual illicit      {fn:>5}              {tp:>5}"
    )


def default_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()