"""Trained-artifact registry.

Artifacts live under ``<repo>/data/models/<model_version>/`` in a layout that
is trivial to audit by hand:

    metadata.json     version pins, dataset provenance, feature schema, metrics
    lightgbm.txt      LightGBM Booster (text dump)
    model_card.md     generated model card
    metrics.json      raw evaluation metrics + confusion matrix

``data/models/`` is git-ignored; a trained artifact is a build output, not
source. ``load_latest()`` returns None when no artifact exists so the runtime
honestly reports ``not_trained`` instead of guessing.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from ml.model import SuspiciousWalletModel

# <repo root>/data/models
DEFAULT_ARTIFACT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "models",
)

_VERSION_RE = re.compile(r"(?P<name>[a-z0-9\-]+)-(?P<version>\d+\.\d+\.\d+)")


def _artifact_root() -> str:
    env_root = os.environ.get("CRYPTOTRACE_MODEL_ROOT")
    return env_root or DEFAULT_ARTIFACT_ROOT


def artifact_dirs(root: Optional[str] = None) -> list:
    """Existing artifact directories, newest model_version first."""
    root = root or _artifact_root()
    if not os.path.isdir(root):
        return []
    dirs = []
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "metadata.json")):
            dirs.append(path)
    return sorted(dirs, key=_version_key, reverse=True)


def _version_key(path: str):
    match = _VERSION_RE.search(os.path.basename(path))
    return tuple(int(part) for part in match.group("version").split(".")) if match else (0, 0, 0)


def latest_path(root: Optional[str] = None) -> Optional[str]:
    dirs = artifact_dirs(root)
    return dirs[0] if dirs else None


def load_latest(root: Optional[str] = None) -> Optional[SuspiciousWalletModel]:
    path = latest_path(root)
    if path is None:
        return None
    try:
        return SuspiciousWalletModel.from_artifact(path)
    except Exception:
        return None


def read_metadata_plans(root: Optional[str] = None) -> list:
    """Metadata dicts for every artifact directory (no HeavyML import)."""
    out = []
    for path in artifact_dirs(root):
        try:
            with open(os.path.join(path, "metadata.json"), encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (OSError, ValueError):
            continue
    return out


def new_model_version(name: str = "lightgbm", major: int = 0) -> str:
    """Next semver for ``name`` within the registry root (e.g. lightgbm-0.0.0)."""
    existing = []
    for path in artifact_dirs():
        match = _VERSION_RE.search(os.path.basename(path))
        if match and match.group("name") == name:
            existing.append(match.group("version"))
    prefix = f"{major}.0."
    candidates = [int(v[len(prefix):]) for v in existing if v.startswith(prefix)]
    patch = (max(candidates) + 1) if candidates else 0
    return f"{name}-{major}.0.{patch}"


def save_artifact(
    model_version: str,
    metadata: dict,
    metrics: dict,
    importances: list,
    booster,
    model_card_md: str,
    root: Optional[str] = None,
) -> str:
    root = root or _artifact_root()
    dest = os.path.join(root, model_version)
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2, sort_keys=True)
    with open(os.path.join(dest, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, sort_keys=True)
    with open(os.path.join(dest, "importances.json"), "w", encoding="utf-8") as fh:
        json.dump({"top_features": importances}, fh, indent=2, sort_keys=True)
    with open(os.path.join(dest, "model_card.md"), "w", encoding="utf-8") as fh:
        fh.write(model_card_md)
    booster.save_model(os.path.join(dest, "lightgbm.txt"))
    return dest