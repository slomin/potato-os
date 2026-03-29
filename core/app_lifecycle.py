"""Dynamic lifecycle module loading for apps that declare lifecycle hooks."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

try:
    from core.app_manifest import AppManifest
except ModuleNotFoundError:
    from app_manifest import AppManifest  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


def load_app_lifecycle(
    manifest: AppManifest,
    app_dir: Path,
):
    """Load an app's lifecycle module, or None if not declared."""
    if not manifest.lifecycle:
        return None

    lifecycle_path = app_dir / manifest.lifecycle
    if not lifecycle_path.is_file():
        logger.warning("App %s declares lifecycle=%s but file not found: %s", manifest.id, manifest.lifecycle, lifecycle_path)
        return None

    try:
        apps_parent = str(app_dir.parent.parent)
        if apps_parent not in sys.path:
            sys.path.insert(0, apps_parent)

        spec = importlib.util.spec_from_file_location(f"app_{manifest.id}_lifecycle", lifecycle_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:
        logger.exception("Failed to load lifecycle for app %s from %s", manifest.id, lifecycle_path)
        return None

    if not hasattr(mod, "on_startup") or not hasattr(mod, "on_shutdown"):
        logger.warning("App %s lifecycle module missing on_startup/on_shutdown: %s", manifest.id, lifecycle_path)
        return None

    return mod
