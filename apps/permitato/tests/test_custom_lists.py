"""Tests for Permitato custom domain lists — per-mode user-defined blocklists."""

from __future__ import annotations

import pytest


def test_add_creates_entry_with_valid_domain(tmp_path):
    from apps.permitato.custom_lists import CustomListStore
    from apps.permitato.exceptions import build_domain_regex

    store = CustomListStore(data_dir=tmp_path)
    entry = store.add("work", "example.com")

    assert entry.mode == "work"
    assert entry.domain == "example.com"
    assert entry.regex_pattern == build_domain_regex("example.com")
    assert entry.id
    assert entry.created_at > 0


def test_add_normalises_domain(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    entry = store.add("work", "  Example.COM  ")

    assert entry.domain == "example.com"


def test_add_rejects_normal_mode(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    with pytest.raises(ValueError, match="normal"):
        store.add("normal", "example.com")


def test_add_rejects_unknown_mode(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    with pytest.raises(ValueError, match="bogus"):
        store.add("bogus", "example.com")


def test_add_rejects_invalid_domain(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    with pytest.raises(ValueError):
        store.add("work", "not-a-domain")


def test_add_rejects_duplicate_same_mode(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    store.add("work", "example.com")
    with pytest.raises(ValueError, match="already exists"):
        store.add("work", "example.com")


def test_add_rejects_duplicate_across_modes(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    store.add("work", "example.com")
    with pytest.raises(ValueError, match="already exists"):
        store.add("sfw", "example.com")


def test_remove_by_id(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    entry = store.add("work", "example.com")
    removed = store.remove(entry.id)

    assert removed.domain == "example.com"
    assert store.list_entries() == []


def test_remove_unknown_raises_keyerror(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    with pytest.raises(KeyError):
        store.remove("nonexistent-id")


def test_list_entries_all(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    store.add("work", "facebook.com")
    store.add("sfw", "adult-site.com")

    entries = store.list_entries()
    assert len(entries) == 2
    domains = {e["domain"] for e in entries}
    assert domains == {"facebook.com", "adult-site.com"}


def test_list_entries_filtered_by_mode(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    store.add("work", "facebook.com")
    store.add("sfw", "adult-site.com")
    store.add("work", "twitter.com")

    work_entries = store.list_entries(mode="work")
    assert len(work_entries) == 2
    assert all(e["mode"] == "work" for e in work_entries)


def test_entries_for_mode_returns_objects(tmp_path):
    from apps.permitato.custom_lists import CustomListStore, CustomDomainEntry

    store = CustomListStore(data_dir=tmp_path)
    store.add("work", "facebook.com")
    store.add("sfw", "adult-site.com")

    work = store.entries_for_mode("work")
    assert len(work) == 1
    assert isinstance(work[0], CustomDomainEntry)
    assert work[0].domain == "facebook.com"


def test_persist_and_load(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    store.add("work", "facebook.com")
    store.add("sfw", "adult-site.com")
    store.persist()

    store2 = CustomListStore(data_dir=tmp_path)
    store2.load()
    assert len(store2.list_entries()) == 2


def test_load_handles_missing_file(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    store = CustomListStore(data_dir=tmp_path)
    store.load()  # should not raise
    assert store.list_entries() == []


def test_load_handles_corrupt_json(tmp_path):
    from apps.permitato.custom_lists import CustomListStore

    (tmp_path / "custom_lists.json").write_text("not json!!!")
    store = CustomListStore(data_dir=tmp_path)
    store.load()  # should not raise
    assert store.list_entries() == []


# ---------------------------------------------------------------------------
# API route tests — direct handler calls with mock state
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_custom_domains_returns_entries(tmp_path):
    state = _make_state(tmp_path)
    state.custom_list_store.add("work", "facebook.com")
    state.custom_list_store.add("sfw", "adult-site.com")

    result = await _call_get_custom_domains(state)
    assert len(result["entries"]) == 2


@pytest.mark.anyio
async def test_get_custom_domains_filters_by_mode(tmp_path):
    state = _make_state(tmp_path)
    state.custom_list_store.add("work", "facebook.com")
    state.custom_list_store.add("sfw", "adult-site.com")

    result = await _call_get_custom_domains(state, mode="work")
    assert len(result["entries"]) == 1
    assert result["entries"][0]["mode"] == "work"


@pytest.mark.anyio
async def test_post_custom_domain_creates_and_syncs_pihole(tmp_path):
    state = _make_state(tmp_path)

    result = await _call_post_custom_domain(state, {
        "mode": "work", "domain": "facebook.com",
    })
    assert result["entry"]["domain"] == "facebook.com"
    assert result["entry"]["mode"] == "work"
    assert len(state.custom_list_store.list_entries()) == 1

    # Verify Pi-hole rule was added
    state.adapter.add_domain_rule.assert_called_once()
    call_kwargs = state.adapter.add_domain_rule.call_args
    assert call_kwargs[1]["rule_type"] == "deny"
    assert call_kwargs[1]["comment"].startswith("Permitato-custom:")


@pytest.mark.anyio
async def test_post_custom_domain_rejects_invalid_domain(tmp_path):
    state = _make_state(tmp_path)

    result, status = await _call_post_custom_domain(
        state, {"mode": "work", "domain": "not-a-domain"}, return_status=True,
    )
    assert status == 400


@pytest.mark.anyio
async def test_post_custom_domain_rejects_invalid_mode(tmp_path):
    state = _make_state(tmp_path)

    result, status = await _call_post_custom_domain(
        state, {"mode": "normal", "domain": "facebook.com"}, return_status=True,
    )
    assert status == 400


@pytest.mark.anyio
async def test_post_custom_domain_rejects_duplicate(tmp_path):
    state = _make_state(tmp_path)
    state.custom_list_store.add("work", "facebook.com")

    result, status = await _call_post_custom_domain(
        state, {"mode": "work", "domain": "facebook.com"}, return_status=True,
    )
    assert status == 400


@pytest.mark.anyio
async def test_post_custom_domain_returns_503_when_not_initialized(tmp_path):
    result, status = await _call_post_custom_domain(
        None, {"mode": "work", "domain": "facebook.com"}, return_status=True,
    )
    assert status == 503


@pytest.mark.anyio
async def test_delete_custom_domain_removes_and_syncs_pihole(tmp_path):
    state = _make_state(tmp_path)
    entry = state.custom_list_store.add("work", "facebook.com")

    result = await _call_delete_custom_domain(state, entry.id)
    assert result["deleted"] is True
    assert len(state.custom_list_store.list_entries()) == 0

    # Verify Pi-hole rule was removed
    state.adapter.delete_domain_rule.assert_called_once()


@pytest.mark.anyio
async def test_delete_custom_domain_keeps_entry_on_pihole_failure(tmp_path):
    from unittest.mock import AsyncMock
    from apps.permitato.pihole_adapter import PiholeUnavailableError

    state = _make_state(tmp_path)
    entry = state.custom_list_store.add("work", "facebook.com")

    state.adapter.delete_domain_rule = AsyncMock(side_effect=PiholeUnavailableError("gone"))

    result, status = await _call_delete_custom_domain(
        state, entry.id, return_status=True,
    )
    assert status == 503

    # Entry must still be in the local store
    assert len(state.custom_list_store.list_entries()) == 1
    # Pi-hole should be marked degraded so compensation runs on reconnect
    assert state.pihole_available is False


@pytest.mark.anyio
async def test_delete_custom_domain_returns_404_for_unknown(tmp_path):
    state = _make_state(tmp_path)

    result, status = await _call_delete_custom_domain(
        state, "nonexistent-id", return_status=True,
    )
    assert status == 404


@pytest.mark.anyio
async def test_status_includes_custom_domain_count(tmp_path):
    state = _make_state(tmp_path)
    state.custom_list_store.add("work", "facebook.com")
    state.custom_list_store.add("sfw", "adult-site.com")

    result = await _call_get_status(state)
    assert result["custom_domain_count"] == 2


# ---------------------------------------------------------------------------
# Test helpers — direct function calls with mock state
# ---------------------------------------------------------------------------


def _make_state(tmp_path):
    from unittest.mock import AsyncMock, MagicMock
    from apps.permitato.custom_lists import CustomListStore
    from apps.permitato.state import PermitState

    adapter = AsyncMock()
    adapter.add_domain_rule = AsyncMock(return_value={})
    adapter.delete_domain_rule = AsyncMock(return_value=None)

    state = PermitState(
        data_dir=tmp_path,
        adapter=adapter,
        pihole_available=True,
        client_id="192.168.1.100",
    )
    state.custom_list_store = CustomListStore(data_dir=tmp_path)
    state.group_map = {"permitato_work": 1, "permitato_sfw": 2, "permitato_exceptions": 3}
    state.exception_group_id = 3
    state.exception_store = MagicMock()
    state.exception_store.active_count.return_value = 0
    state.exception_store.list_active.return_value = []
    state.schedule_store = MagicMock()
    state.schedule_store.evaluate.return_value = None
    return state


async def _call_get_custom_domains(state, mode=None):
    from unittest.mock import MagicMock
    request = MagicMock()
    request.app.state.permit_state = state
    request.query_params = {"mode": mode} if mode else {}

    from apps.permitato.routes import get_custom_domains
    return await get_custom_domains(request)


async def _call_post_custom_domain(state, body, return_status=False):
    from unittest.mock import AsyncMock, MagicMock
    request = MagicMock()
    request.app.state.permit_state = state
    request.json = AsyncMock(return_value=body)

    from apps.permitato.routes import add_custom_domain
    result = await add_custom_domain(request)
    if return_status:
        if hasattr(result, "status_code"):
            import json
            return json.loads(result.body.decode()), result.status_code
        return result, 200
    return result


async def _call_delete_custom_domain(state, entry_id, return_status=False):
    from unittest.mock import MagicMock
    request = MagicMock()
    request.app.state.permit_state = state

    from apps.permitato.routes import delete_custom_domain
    result = await delete_custom_domain(request, entry_id)
    if return_status:
        if hasattr(result, "status_code"):
            import json
            return json.loads(result.body.decode()), result.status_code
        return result, 200
    return result


async def _call_get_status(state):
    from unittest.mock import patch
    from apps.permitato import routes

    from unittest.mock import MagicMock
    request = MagicMock()
    request.app.state.permit_state = state

    return await routes.permitato_status(request)
