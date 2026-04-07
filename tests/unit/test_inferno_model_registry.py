"""Tests for core.inferno.model_registry — format, settings, file ops, and state management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    from core.inferno.model_registry import (
        VALID_MODEL_EXTENSIONS,
        DEFAULT_MODEL_CHAT_SETTINGS,
        DEFAULT_MODEL_VISION_SETTINGS,
        MODELS_STATE_VERSION,
        ModelSettingsValidationError,
        ModelStoreConfig,
        model_format_for_filename,
        validate_model_url,
        _has_valid_model_extension,
        _sanitize_filename,
        _slugify_id,
        _unique_model_id,
        _unique_filename,
        is_qwen35_a3b_filename,
        model_supports_vision_filename,
        normalize_model_settings,
        build_model_capabilities,
        apply_model_chat_defaults,
        get_model_by_id,
        _is_discoverable_local_model_filename,
        model_file_path,
        model_file_present,
        describe_model_storage,
        resolve_model_runtime_path,
        discover_local_model_filenames,
        ensure_models_state,
        save_models_state,
        register_model_url,
        delete_model,
        update_model_settings,
        any_model_ready,
    )
except ModuleNotFoundError:
    from inferno.model_registry import (  # type: ignore[no-redef]
        VALID_MODEL_EXTENSIONS,
        DEFAULT_MODEL_CHAT_SETTINGS,
        DEFAULT_MODEL_VISION_SETTINGS,
        MODELS_STATE_VERSION,
        ModelSettingsValidationError,
        ModelStoreConfig,
        model_format_for_filename,
        validate_model_url,
        _has_valid_model_extension,
        _sanitize_filename,
        _slugify_id,
        _unique_model_id,
        _unique_filename,
        is_qwen35_a3b_filename,
        model_supports_vision_filename,
        normalize_model_settings,
        build_model_capabilities,
        apply_model_chat_defaults,
        get_model_by_id,
        _is_discoverable_local_model_filename,
        model_file_path,
        model_file_present,
        describe_model_storage,
        resolve_model_runtime_path,
        discover_local_model_filenames,
        ensure_models_state,
        save_models_state,
        register_model_url,
        delete_model,
        update_model_settings,
        any_model_ready,
    )


@pytest.fixture
def store(tmp_path: Path) -> ModelStoreConfig:
    """Create a ModelStoreConfig backed by a temp directory."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    state_path = tmp_path / "state" / "models.json"
    state_path.parent.mkdir()
    return ModelStoreConfig(
        models_dir=models_dir,
        state_path=state_path,
        default_filename="default-model.gguf",
        default_url="https://example.com/default-model.gguf",
        known_default_filenames=("default-model.gguf",),
        current_model_filename="",
    )


# -- Constants --


def test_valid_model_extensions():
    assert ".gguf" in VALID_MODEL_EXTENSIONS
    assert ".litertlm" in VALID_MODEL_EXTENSIONS


def test_state_version_is_int():
    assert isinstance(MODELS_STATE_VERSION, int)


def test_default_chat_settings_has_required_keys():
    for key in ("temperature", "top_p", "top_k", "max_tokens", "stream"):
        assert key in DEFAULT_MODEL_CHAT_SETTINGS


def test_default_vision_settings_has_required_keys():
    for key in ("enabled", "projector_mode", "projector_filename"):
        assert key in DEFAULT_MODEL_VISION_SETTINGS


# -- Format detection --


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("model.gguf", "gguf"),
        ("MODEL.GGUF", "gguf"),
        ("model.litertlm", "litertlm"),
        ("Model.LiteRTLM", "litertlm"),
        ("anything-else.bin", "gguf"),
    ],
)
def test_model_format_for_filename(filename, expected):
    assert model_format_for_filename(filename) == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("model.gguf", True),
        ("model.GGUF", True),
        ("model.litertlm", True),
        ("model.bin", False),
        ("model.safetensors", False),
    ],
)
def test_has_valid_model_extension(filename, expected):
    assert _has_valid_model_extension(filename) == expected


# -- URL validation --


def test_validate_model_url_valid():
    ok, reason, name = validate_model_url("https://example.com/model.gguf")
    assert ok is True
    assert reason == ""
    assert name == "model.gguf"


def test_validate_model_url_http_rejected():
    ok, reason, _ = validate_model_url("http://example.com/model.gguf")
    assert ok is False
    assert reason == "https_required"


def test_validate_model_url_no_filename():
    ok, reason, _ = validate_model_url("https://example.com/")
    assert ok is False
    assert reason == "filename_missing"


def test_validate_model_url_bad_extension():
    ok, reason, _ = validate_model_url("https://example.com/model.bin")
    assert ok is False
    assert reason == "unsupported_model_format"


def test_validate_model_url_litertlm():
    ok, reason, name = validate_model_url("https://example.com/model.litertlm")
    assert ok is True
    assert name == "model.litertlm"


# -- Filename / ID utilities --


def test_sanitize_filename_basic():
    assert _sanitize_filename("model.gguf") == "model.gguf"


def test_sanitize_filename_special_chars():
    result = _sanitize_filename("my model (v2).gguf")
    assert result.endswith(".gguf")
    assert " " not in result
    assert "(" not in result


def test_sanitize_filename_empty():
    assert _sanitize_filename("") == "model.gguf"


def test_slugify_id():
    assert _slugify_id("My Model-V2") == "my-model-v2"


def test_slugify_id_empty():
    assert _slugify_id("") == "model"


def test_unique_model_id_no_conflict():
    assert _unique_model_id("base", set()) == "base"


def test_unique_model_id_with_conflict():
    assert _unique_model_id("base", {"base"}) == "base-2"
    assert _unique_model_id("base", {"base", "base-2"}) == "base-3"


def test_unique_filename_no_conflict():
    assert _unique_filename("model.gguf", set()) == "model.gguf"


def test_unique_filename_with_conflict():
    assert _unique_filename("model.gguf", {"model.gguf"}) == "model-2.gguf"


# -- Model detection --


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("Qwen3.5-35B-A3B-Q4_K_M.gguf", True),
        ("qwen-3.5-35b-a3b-q4.gguf", True),
        ("Qwen3.5-2B-Q4_K_M.gguf", False),
        (None, False),
        ("", False),
    ],
)
def test_is_qwen35_a3b_filename(filename, expected):
    assert is_qwen35_a3b_filename(filename) == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("Qwen3.5-2B-Q4_K_M.gguf", True),
        ("Qwen3-VL-2B-Q4.gguf", True),
        ("gemma-4-E2B-it-Q4_K_M.gguf", True),
        ("llama-3.2-1B.gguf", False),
        (None, False),
        ("", False),
    ],
)
def test_model_supports_vision_filename(filename, expected):
    assert model_supports_vision_filename(filename) == expected


# -- Settings normalization --


def test_normalize_model_settings_defaults():
    result = normalize_model_settings(None, filename="model.gguf")
    assert "chat" in result
    assert "vision" in result
    assert result["chat"]["temperature"] == DEFAULT_MODEL_CHAT_SETTINGS["temperature"]


def test_normalize_model_settings_preserves_values():
    raw = {"chat": {"temperature": 0.5}}
    result = normalize_model_settings(raw, filename="model.gguf")
    assert result["chat"]["temperature"] == 0.5


def test_normalize_model_settings_invalid_float_raises():
    raw = {"chat": {"temperature": "not_a_number"}}
    with pytest.raises(ModelSettingsValidationError):
        normalize_model_settings(raw, filename="model.gguf")


def test_normalize_model_settings_vision_enabled_for_vision_model():
    result = normalize_model_settings(None, filename="Qwen3.5-2B-Q4_K_M.gguf")
    assert result["vision"]["enabled"] is True


def test_normalize_model_settings_vision_disabled_for_non_vision():
    result = normalize_model_settings(None, filename="llama-3.2.gguf")
    assert result["vision"]["enabled"] is False


def test_normalize_vision_projector_mode_validates():
    raw = {"vision": {"projector_mode": "bogus"}}
    result = normalize_model_settings(raw, filename="model.gguf")
    assert result["vision"]["projector_mode"] == "default"


# -- Capabilities --


def test_build_model_capabilities_vision():
    caps = build_model_capabilities("Qwen3.5-2B-Q4_K_M.gguf")
    assert caps["vision"] is True


def test_build_model_capabilities_no_vision():
    caps = build_model_capabilities("llama-3.2-1B.gguf")
    assert caps["vision"] is False


# -- Chat defaults --


def test_apply_model_chat_defaults_a3b_adds_thinking():
    payload = {"messages": []}
    result = apply_model_chat_defaults(payload, active_model_filename="Qwen3.5-35B-A3B-Q4.gguf")
    assert result["chat_template_kwargs"]["enable_thinking"] is False


def test_apply_model_chat_defaults_non_a3b_unchanged():
    payload = {"messages": []}
    result = apply_model_chat_defaults(payload, active_model_filename="Qwen3.5-2B-Q4.gguf")
    assert result is payload


def test_apply_model_chat_defaults_preserves_explicit_thinking():
    payload = {"messages": [], "chat_template_kwargs": {"enable_thinking": True}}
    result = apply_model_chat_defaults(payload, active_model_filename="Qwen3.5-35B-A3B-Q4.gguf")
    assert result["chat_template_kwargs"]["enable_thinking"] is True


# -- get_model_by_id --


def test_get_model_by_id_found():
    state = {"models": [{"id": "a"}, {"id": "b"}]}
    assert get_model_by_id(state, "b") == {"id": "b"}


def test_get_model_by_id_missing():
    state = {"models": [{"id": "a"}]}
    assert get_model_by_id(state, "missing") is None


def test_get_model_by_id_empty():
    assert get_model_by_id({"models": []}, "x") is None


# -- Discoverable filenames --


def test_discoverable_gguf():
    assert _is_discoverable_local_model_filename("model.gguf") is True


def test_discoverable_litertlm():
    assert _is_discoverable_local_model_filename("model.litertlm") is True


def test_discoverable_rejects_mmproj():
    assert _is_discoverable_local_model_filename("mmproj-F16.gguf") is False
    assert _is_discoverable_local_model_filename("mmproj-model-f16.gguf") is False


def test_discoverable_rejects_bad_extension():
    assert _is_discoverable_local_model_filename("model.bin") is False


# -- File / path operations --


def test_model_file_path(tmp_path):
    result = model_file_path(tmp_path / "models", "test.gguf")
    assert result == tmp_path / "models" / "test.gguf"


def test_model_file_present_true(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "model.gguf").write_bytes(b"data")
    assert model_file_present(models_dir, "model.gguf") is True


def test_model_file_present_false(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    assert model_file_present(models_dir, "model.gguf") is False


def test_model_file_present_empty_file(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "model.gguf").write_bytes(b"")
    assert model_file_present(models_dir, "model.gguf") is False


def test_describe_model_storage_exists(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "model.gguf").write_bytes(b"x" * 100)
    result = describe_model_storage(models_dir, "model.gguf")
    assert result["exists"] is True
    assert result["size_bytes"] == 100
    assert result["location"] == "local"


def test_describe_model_storage_missing(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    result = describe_model_storage(models_dir, "model.gguf")
    assert result["exists"] is False
    assert result["size_bytes"] == 0


def test_resolve_model_runtime_path_regular(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "model.gguf").write_bytes(b"data")
    result = resolve_model_runtime_path(models_dir, "model.gguf")
    assert result == models_dir / "model.gguf"


def test_resolve_model_runtime_path_symlink(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    real = tmp_path / "real.gguf"
    real.write_bytes(b"data")
    (models_dir / "model.gguf").symlink_to(real)
    result = resolve_model_runtime_path(models_dir, "model.gguf")
    assert result == real.resolve()


def test_discover_local_model_filenames(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "alpha.gguf").write_bytes(b"a")
    (models_dir / "beta.litertlm").write_bytes(b"b")
    (models_dir / "mmproj-F16.gguf").write_bytes(b"p")
    (models_dir / "readme.txt").write_bytes(b"r")
    result = discover_local_model_filenames(models_dir)
    assert "alpha.gguf" in result
    assert "beta.litertlm" in result
    assert "mmproj-F16.gguf" not in result
    assert "readme.txt" not in result


def test_discover_local_model_filenames_empty(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    assert discover_local_model_filenames(models_dir) == []


# -- State management (ModelStoreConfig) --


def test_ensure_models_state_creates_default(store):
    state = ensure_models_state(store)
    assert state["version"] == MODELS_STATE_VERSION
    assert len(state["models"]) >= 1
    default = state["models"][0]
    assert default["id"] == "default"
    assert default["filename"] == "default-model.gguf"
    assert store.state_path.exists()


def test_ensure_models_state_reads_existing(store):
    raw = {
        "version": 1,
        "models": [{"id": "custom", "filename": "custom.gguf", "source_url": None, "source_type": "upload", "status": "ready"}],
        "active_model_id": "custom",
    }
    store.state_path.write_text(json.dumps(raw), encoding="utf-8")
    state = ensure_models_state(store)
    ids = [m["id"] for m in state["models"]]
    assert "custom" in ids


def test_ensure_models_state_marks_default_downloaded_once(store):
    (store.models_dir / "default-model.gguf").write_bytes(b"model-data")
    state = ensure_models_state(store)
    assert state["default_model_downloaded_once"] is True


def test_save_models_state_normalizes_and_persists(store):
    ensure_models_state(store)
    state = {"models": [{"id": "x", "filename": "x.gguf"}], "active_model_id": "x"}
    saved = save_models_state(store, state)
    assert saved["version"] == MODELS_STATE_VERSION
    reloaded = json.loads(store.state_path.read_text(encoding="utf-8"))
    assert reloaded["version"] == MODELS_STATE_VERSION


def test_register_model_url_adds_model(store):
    ensure_models_state(store)
    ok, reason, model = register_model_url(store, "https://example.com/new-model.gguf")
    assert ok is True
    assert reason == "registered"
    assert model["filename"] == "new-model.gguf"


def test_register_model_url_detects_duplicate(store):
    ensure_models_state(store)
    register_model_url(store, "https://example.com/dup.gguf")
    ok, reason, _ = register_model_url(store, "https://example.com/dup.gguf")
    assert ok is True
    assert reason == "already_exists"


def test_register_model_url_rejects_http(store):
    ensure_models_state(store)
    ok, reason, _ = register_model_url(store, "http://example.com/model.gguf")
    assert ok is False
    assert reason == "https_required"


def test_delete_model_removes_file(store):
    ensure_models_state(store)
    register_model_url(store, "https://example.com/to-delete.gguf")
    (store.models_dir / "to-delete.gguf").write_bytes(b"data")
    ok, reason, deleted_file, freed, was_active = delete_model(store, model_id="to-delete")
    assert ok is True
    assert reason == "deleted"
    assert deleted_file is True
    assert freed > 0
    assert not (store.models_dir / "to-delete.gguf").exists()


def test_delete_model_not_found(store):
    ensure_models_state(store)
    ok, reason, _, _, _ = delete_model(store, model_id="nonexistent")
    assert ok is False
    assert reason == "model_not_found"


def test_update_model_settings_persists(store):
    ensure_models_state(store)
    ok, reason, updated = update_model_settings(
        store, model_id="default", settings={"chat": {"temperature": 0.3}}
    )
    assert ok is True
    assert reason == "updated"
    assert updated["settings"]["chat"]["temperature"] == 0.3


def test_update_model_settings_not_found(store):
    ensure_models_state(store)
    ok, reason, _ = update_model_settings(store, model_id="nope", settings={})
    assert ok is False
    assert reason == "model_not_found"


def test_any_model_ready_false(store):
    ensure_models_state(store)
    assert any_model_ready(store) is False


def test_any_model_ready_true(store):
    ensure_models_state(store)
    (store.models_dir / "default-model.gguf").write_bytes(b"data")
    assert any_model_ready(store) is True
