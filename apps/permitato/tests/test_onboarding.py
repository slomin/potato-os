"""Tests for Permitato client validation, discovery, and onboarding."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest


FAKE_CLIENTS = [
    {"client": "192.168.1.106", "name": "", "id": 1, "groups": [0, 3]},
    {"client": "192.168.1.200", "name": "iPhone", "id": 2, "groups": [0]},
]


# ---------------------------------------------------------------------------
# validate_client
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_validate_client_true_when_exists(tmp_path):
    from apps.permitato.state import PermitState, validate_client

    adapter = AsyncMock()
    adapter.get_clients = AsyncMock(return_value=FAKE_CLIENTS)

    state = PermitState(
        data_dir=tmp_path,
        adapter=adapter,
        pihole_available=True,
        client_id="192.168.1.106",
    )

    result = await validate_client(state)

    assert result is True
    assert state.client_valid is True


@pytest.mark.anyio
async def test_validate_client_false_when_missing(tmp_path):
    from apps.permitato.state import PermitState, validate_client

    adapter = AsyncMock()
    adapter.get_clients = AsyncMock(return_value=FAKE_CLIENTS)

    state = PermitState(
        data_dir=tmp_path,
        adapter=adapter,
        pihole_available=True,
        client_id="10.0.0.99",
    )

    result = await validate_client(state)

    assert result is False
    assert state.client_valid is False


@pytest.mark.anyio
async def test_validate_client_none_when_no_client_id(tmp_path):
    from apps.permitato.state import PermitState, validate_client

    state = PermitState(
        data_dir=tmp_path,
        adapter=AsyncMock(),
        pihole_available=True,
        client_id="",
    )

    result = await validate_client(state)

    assert result is None
    assert state.client_valid is None


@pytest.mark.anyio
async def test_validate_client_none_when_pihole_unavailable(tmp_path):
    from apps.permitato.state import PermitState, validate_client

    state = PermitState(
        data_dir=tmp_path,
        adapter=AsyncMock(),
        pihole_available=False,
        client_id="192.168.1.106",
    )

    result = await validate_client(state)

    assert result is None
    assert state.client_valid is None


@pytest.mark.anyio
async def test_validate_client_caches_for_30s(tmp_path):
    from apps.permitato.state import PermitState, validate_client

    adapter = AsyncMock()
    adapter.get_clients = AsyncMock(return_value=FAKE_CLIENTS)

    state = PermitState(
        data_dir=tmp_path,
        adapter=adapter,
        pihole_available=True,
        client_id="192.168.1.106",
    )

    await validate_client(state)
    await validate_client(state)

    # Should only have called get_clients once (cached)
    adapter.get_clients.assert_awaited_once()


@pytest.mark.anyio
async def test_validate_client_refreshes_after_expiry(tmp_path):
    from apps.permitato.state import PermitState, validate_client

    adapter = AsyncMock()
    adapter.get_clients = AsyncMock(return_value=FAKE_CLIENTS)

    state = PermitState(
        data_dir=tmp_path,
        adapter=adapter,
        pihole_available=True,
        client_id="192.168.1.106",
    )

    await validate_client(state)

    # Expire the cache manually
    state._client_cache_ts = time.time() - 31

    await validate_client(state)

    assert adapter.get_clients.await_count == 2


@pytest.mark.anyio
async def test_validate_client_force_refresh_bypasses_cache(tmp_path):
    from apps.permitato.state import PermitState, validate_client

    adapter = AsyncMock()
    adapter.get_clients = AsyncMock(return_value=FAKE_CLIENTS)

    state = PermitState(
        data_dir=tmp_path,
        adapter=adapter,
        pihole_available=True,
        client_id="192.168.1.106",
    )

    await validate_client(state)
    await validate_client(state, force_refresh=True)

    assert adapter.get_clients.await_count == 2


@pytest.mark.anyio
async def test_validate_client_backs_off_on_pihole_failure(tmp_path):
    from apps.permitato.pihole_adapter import PiholeUnavailableError
    from apps.permitato.state import PermitState, validate_client

    adapter = AsyncMock()
    adapter.get_clients = AsyncMock(side_effect=PiholeUnavailableError("down"))

    state = PermitState(
        data_dir=tmp_path,
        adapter=adapter,
        pihole_available=True,
        client_id="192.168.1.106",
    )

    await validate_client(state)
    assert state.client_valid is None
    assert state.pihole_available is False
    assert state.degraded_since is not None

    # Second call returns early (pihole_available is now False)
    await validate_client(state)
    adapter.get_clients.assert_awaited_once()


# ---------------------------------------------------------------------------
# resolve_requester_ipv4
# ---------------------------------------------------------------------------


def test_resolve_direct_ipv4_match():
    from apps.permitato.net_resolve import resolve_requester_ipv4

    result = resolve_requester_ipv4("192.168.1.106", {"192.168.1.106", "10.0.0.1"})
    assert result == "192.168.1.106"


def test_resolve_strips_ipv4_mapped_ipv6():
    from apps.permitato.net_resolve import resolve_requester_ipv4

    result = resolve_requester_ipv4("::ffff:192.168.1.106", {"192.168.1.106"})
    assert result == "192.168.1.106"


def test_resolve_returns_none_for_unknown():
    from apps.permitato.net_resolve import resolve_requester_ipv4

    # No neighbor table on macOS/test environment — falls through to None
    result = resolve_requester_ipv4("2001:db8::1234", {"192.168.1.106"})
    assert result is None


def test_resolve_returns_none_for_empty():
    from apps.permitato.net_resolve import resolve_requester_ipv4

    assert resolve_requester_ipv4("", {"192.168.1.106"}) is None
    assert resolve_requester_ipv4(None, {"192.168.1.106"}) is None


# ---------------------------------------------------------------------------
# GET /clients
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_clients_marks_selected(tmp_path):
    from apps.permitato.state import PermitState
    from apps.permitato.routes import router
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    adapter = AsyncMock()
    adapter.get_clients = AsyncMock(return_value=FAKE_CLIENTS)

    state = PermitState(
        data_dir=tmp_path,
        adapter=adapter,
        pihole_available=True,
        client_id="192.168.1.106",
    )

    app = FastAPI()
    app.include_router(router)
    app.state.permit_state = state

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/clients")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["clients"]) == 2
    assert data["pihole_available"] is True

    selected = [c for c in data["clients"] if c["selected"]]
    assert len(selected) == 1
    assert selected[0]["client"] == "192.168.1.106"


@pytest.mark.anyio
async def test_get_clients_empty_when_pihole_down(tmp_path):
    from apps.permitato.state import PermitState
    from apps.permitato.routes import router
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    state = PermitState(
        data_dir=tmp_path,
        adapter=None,
        pihole_available=False,
    )

    app = FastAPI()
    app.include_router(router)
    app.state.permit_state = state

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/clients")

    assert resp.status_code == 200
    data = resp.json()
    assert data["clients"] == []
    assert data["pihole_available"] is False


# ---------------------------------------------------------------------------
# POST /client validation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_post_client_warns_when_unknown(tmp_path):
    from apps.permitato.state import PermitState
    from apps.permitato.routes import router
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    adapter = AsyncMock()
    adapter.get_clients = AsyncMock(return_value=FAKE_CLIENTS)
    adapter.update_client = AsyncMock()

    state = PermitState(
        data_dir=tmp_path,
        adapter=adapter,
        pihole_available=True,
    )
    state.exception_store = MagicMock()

    app = FastAPI()
    app.include_router(router)
    app.state.permit_state = state

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/client", json={"client_id": "10.0.0.99"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["client_id"] == "10.0.0.99"
    assert data["warning"] is not None


@pytest.mark.anyio
async def test_post_client_no_warning_when_known(tmp_path):
    from apps.permitato.state import PermitState
    from apps.permitato.routes import router
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    adapter = AsyncMock()
    adapter.get_clients = AsyncMock(return_value=FAKE_CLIENTS)
    adapter.update_client = AsyncMock()

    state = PermitState(
        data_dir=tmp_path,
        adapter=adapter,
        pihole_available=True,
    )
    state.exception_store = MagicMock()

    app = FastAPI()
    app.include_router(router)
    app.state.permit_state = state

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/client", json={"client_id": "192.168.1.106"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["client_id"] == "192.168.1.106"
    assert data["client_valid"] is True
    assert data.get("warning") is None
