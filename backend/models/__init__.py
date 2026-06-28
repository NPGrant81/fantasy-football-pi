"""Compatibility shim for ORM model imports.

This repository has both:
- backend/models.py (legacy module containing ORM classes)
- backend/models/ (package for model-adjacent modules)

On some Python environments, ``import backend.models`` can resolve to this
package instead of the legacy module, which breaks call sites expecting ORM
classes like ``RefreshToken``. To keep both import styles working, this shim
loads ``backend/models.py`` under an internal name and re-exports its public
symbols from the package namespace.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_LEGACY_MODELS_PATH = Path(__file__).resolve().parents[1] / "models.py"
_LEGACY_MODULE_NAME = "backend._legacy_models"

_spec = spec_from_file_location(_LEGACY_MODULE_NAME, _LEGACY_MODELS_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load ORM models module at {_LEGACY_MODELS_PATH}")

_legacy_models = module_from_spec(_spec)
_spec.loader.exec_module(_legacy_models)

for _name in dir(_legacy_models):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_legacy_models, _name)

# Keep import * behavior stable for callers that rely on model exports.
__all__ = [name for name in dir(_legacy_models) if not name.startswith("_")]
