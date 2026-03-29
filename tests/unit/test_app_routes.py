"""Tests for the app-provided routes framework extension."""

from pathlib import Path

import pytest

from tests.unit.conftest import REPO_ROOT


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------


def test_manifest_with_routes_field_parses():
    from core.app_manifest import AppManifest

    manifest = AppManifest(
        id="test", name="Test", entry="main.py", routes="routes.py",
    )
    assert manifest.routes == "routes.py"


def test_manifest_without_routes_defaults_to_empty():
    from core.app_manifest import AppManifest

    manifest = AppManifest(id="test", name="Test", entry="main.py")
    assert manifest.routes == ""


def test_manifest_from_file_parses_routes(tmp_path):
    import json
    from core.app_manifest import AppManifest

    manifest_path = tmp_path / "app.json"
    manifest_path.write_text(json.dumps({
        "id": "myapp",
        "name": "My App",
        "entry": "main.py",
        "routes": "routes.py",
    }))
    manifest = AppManifest.from_file(manifest_path)
    assert manifest.routes == "routes.py"


def test_manifest_from_file_without_routes_field(tmp_path):
    import json
    from core.app_manifest import AppManifest

    manifest_path = tmp_path / "app.json"
    manifest_path.write_text(json.dumps({
        "id": "myapp",
        "name": "My App",
        "entry": "main.py",
    }))
    manifest = AppManifest.from_file(manifest_path)
    assert manifest.routes == ""


# ---------------------------------------------------------------------------
# Existing apps unaffected
# ---------------------------------------------------------------------------


def test_skeleton_manifest_still_valid():
    """Existing skeleton app must still parse and validate with the new field."""
    from core.app_manifest import AppManifest

    manifest_path = REPO_ROOT / "apps" / "skeleton" / "app.json"
    manifest = AppManifest.from_file(manifest_path)
    errors = manifest.validate()
    assert errors == []
    assert manifest.routes == ""


def test_chat_manifest_still_valid():
    """Existing chat app must still parse and validate with the new field."""
    from core.app_manifest import AppManifest

    manifest_path = REPO_ROOT / "apps" / "chat" / "app.json"
    manifest = AppManifest.from_file(manifest_path)
    errors = manifest.validate()
    assert errors == []


# ---------------------------------------------------------------------------
# Router loading
# ---------------------------------------------------------------------------


def test_app_router_mounted_at_correct_prefix(tmp_path):
    """An app with routes.py gets its router mounted at /app/{id}/api/."""
    import json
    from core.app_manifest import AppManifest

    # Create a minimal app with a routes module
    app_dir = tmp_path / "apps" / "testapp"
    app_dir.mkdir(parents=True)
    (app_dir / "app.json").write_text(json.dumps({
        "id": "testapp",
        "name": "Test App",
        "entry": "main.py",
        "routes": "routes.py",
    }))
    (app_dir / "routes.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/ping')\n"
        "async def ping():\n"
        "    return {'pong': True}\n"
    )

    from core.app_manifest import discover_apps
    from core.app_routes import load_app_router

    manifests = discover_apps(tmp_path / "apps")
    assert len(manifests) == 1

    router, prefix = load_app_router(manifests[0], app_dir)
    assert router is not None
    assert prefix == "/app/testapp/api"


def test_load_app_router_returns_none_when_no_routes(tmp_path):
    """An app without routes field returns None."""
    import json
    from core.app_manifest import AppManifest

    app_dir = tmp_path / "apps" / "noroutes"
    app_dir.mkdir(parents=True)
    (app_dir / "app.json").write_text(json.dumps({
        "id": "noroutes",
        "name": "No Routes",
        "entry": "main.py",
    }))

    from core.app_routes import load_app_router
    from core.app_manifest import AppManifest

    manifest = AppManifest.from_file(app_dir / "app.json")
    result = load_app_router(manifest, app_dir)
    assert result is None


def test_load_app_router_returns_none_when_file_missing(tmp_path):
    """If routes file doesn't exist, return None and don't crash."""
    from core.app_manifest import AppManifest
    from core.app_routes import load_app_router

    app_dir = tmp_path / "apps" / "broken"
    app_dir.mkdir(parents=True)

    manifest = AppManifest(
        id="broken", name="Broken", entry="main.py", routes="routes.py",
    )
    result = load_app_router(manifest, app_dir)
    assert result is None


# ---------------------------------------------------------------------------
# route_prefix — None vs empty string matters
# ---------------------------------------------------------------------------


def test_manifest_route_prefix_none_by_default():
    from core.app_manifest import AppManifest

    manifest = AppManifest(id="t", name="T", entry="main.py")
    assert manifest.route_prefix is None


def test_manifest_route_prefix_parses_empty_string(tmp_path):
    import json
    from core.app_manifest import AppManifest

    p = tmp_path / "app.json"
    p.write_text(json.dumps({"id": "t", "name": "T", "entry": "main.py", "route_prefix": ""}))
    m = AppManifest.from_file(p)
    assert m.route_prefix == ""


def test_load_app_router_uses_custom_prefix(tmp_path):
    from core.app_manifest import AppManifest
    from core.app_routes import load_app_router

    app_dir = tmp_path / "apps" / "myapp"
    app_dir.mkdir(parents=True)
    (app_dir / "routes.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n"
    )
    manifest = AppManifest(id="myapp", name="My", entry="main.py", routes="routes.py", route_prefix="")
    _, prefix = load_app_router(manifest, app_dir)
    assert prefix == ""


def test_load_app_router_uses_default_prefix_when_none(tmp_path):
    from core.app_manifest import AppManifest
    from core.app_routes import load_app_router

    app_dir = tmp_path / "apps" / "myapp"
    app_dir.mkdir(parents=True)
    (app_dir / "routes.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n"
    )
    manifest = AppManifest(id="myapp", name="My", entry="main.py", routes="routes.py")
    _, prefix = load_app_router(manifest, app_dir)
    assert prefix == "/app/myapp/api"


# ---------------------------------------------------------------------------
# Lifecycle module loading
# ---------------------------------------------------------------------------


def test_load_app_lifecycle_returns_module(tmp_path):
    from core.app_manifest import AppManifest
    from core.app_lifecycle import load_app_lifecycle

    app_dir = tmp_path / "apps" / "myapp"
    app_dir.mkdir(parents=True)
    (app_dir / "lifecycle.py").write_text(
        "async def on_startup(app, app_dir, data_dir): pass\n"
        "async def on_shutdown(app): pass\n"
    )
    manifest = AppManifest(id="myapp", name="My", entry="main.py", lifecycle="lifecycle.py")
    mod = load_app_lifecycle(manifest, app_dir)
    assert mod is not None
    assert hasattr(mod, "on_startup")
    assert hasattr(mod, "on_shutdown")


def test_load_app_lifecycle_returns_none_when_not_declared():
    from core.app_manifest import AppManifest
    from core.app_lifecycle import load_app_lifecycle
    from pathlib import Path

    manifest = AppManifest(id="t", name="T", entry="main.py")
    assert load_app_lifecycle(manifest, Path("/nonexistent")) is None


def test_load_app_lifecycle_returns_none_when_file_missing(tmp_path):
    from core.app_manifest import AppManifest
    from core.app_lifecycle import load_app_lifecycle

    manifest = AppManifest(id="t", name="T", entry="main.py", lifecycle="lifecycle.py")
    assert load_app_lifecycle(manifest, tmp_path) is None
