"""Model registry, format handling, and settings normalization for Inferno.

This module owns the model lifecycle logic that is inference-owned:
format detection, URL validation, filename sanitization, settings
normalization, registry CRUD, file operations, and projector download.

Product-specific defaults (device class, default model selection) are
injected via ModelStoreConfig — this module never imports from
core.model_state, core.runtime_state, or any Potato-specific code.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
from pathlib import Path
from typing import Any

logger = __import__("logging").getLogger("potato")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_MODEL_EXTENSIONS = (".gguf", ".litertlm")

MODELS_STATE_VERSION = 1

DEFAULT_MODEL_CHAT_SETTINGS = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "repetition_penalty": 1.0,
    "presence_penalty": 1.5,
    "max_tokens": 16384,
    "stream": True,
    "generation_mode": "random",
    "seed": 42,
    "system_prompt": "",
    "cache_prompt": True,
}

DEFAULT_MODEL_VISION_SETTINGS = {
    "enabled": False,
    "projector_mode": "default",
    "projector_filename": None,
}


# ---------------------------------------------------------------------------
# Store configuration
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ModelStoreConfig:
    """Filesystem and product-policy context for model registry operations.

    This bundles the paths and defaults that the Potato layer injects so
    that Inferno never needs to import RuntimeConfig.
    """

    models_dir: Path
    state_path: Path
    default_filename: str
    default_url: str
    known_default_filenames: tuple[str, ...]
    current_model_filename: str


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ModelSettingsValidationError(ValueError):
    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


# ---------------------------------------------------------------------------
# Format detection & URL validation
# ---------------------------------------------------------------------------


def model_format_for_filename(filename: str) -> str:
    if filename.lower().endswith(".litertlm"):
        return "litertlm"
    return "gguf"


def _has_valid_model_extension(filename: str) -> bool:
    lower = filename.lower()
    return any(lower.endswith(ext) for ext in VALID_MODEL_EXTENSIONS)


def validate_model_url(source_url: str) -> tuple[bool, str, str]:
    from urllib.parse import unquote, urlparse

    parsed = urlparse(source_url.strip())
    if parsed.scheme != "https":
        return False, "https_required", ""
    basename = unquote(Path(parsed.path).name)
    if not basename:
        return False, "filename_missing", ""
    if not _has_valid_model_extension(basename):
        return False, "unsupported_model_format", ""
    safe_name = _sanitize_filename(basename)
    if not _has_valid_model_extension(safe_name):
        safe_name = f"{Path(safe_name).stem}.gguf"
    return True, "", safe_name


# ---------------------------------------------------------------------------
# Filename / ID utilities
# ---------------------------------------------------------------------------


def _sanitize_filename(filename: str) -> str:
    candidate = Path(filename).name.strip()
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate)
    candidate = candidate.lstrip(".")
    return candidate or "model.gguf"


def _slugify_id(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return slug or "model"


def _unique_model_id(base_id: str, existing_ids: set[str]) -> str:
    candidate = base_id
    idx = 2
    while candidate in existing_ids:
        candidate = f"{base_id}-{idx}"
        idx += 1
    return candidate


def _unique_filename(base_name: str, existing_names: set[str]) -> str:
    stem = Path(base_name).stem
    suffix = Path(base_name).suffix or ".gguf"
    candidate = f"{stem}{suffix}"
    idx = 2
    while candidate in existing_names:
        candidate = f"{stem}-{idx}{suffix}"
        idx += 1
    return candidate


# ---------------------------------------------------------------------------
# Model detection
# ---------------------------------------------------------------------------


def is_qwen35_a3b_filename(filename: str | None) -> bool:
    value = str(filename or "").strip().lower()
    return bool(value) and "qwen" in value and "3.5" in value and "35b" in value and "a3b" in value


def model_supports_vision_filename(filename: str | None) -> bool:
    value = str(filename or "").strip().lower()
    if not value:
        return False
    if "qwen3" in value and "vl" in value:
        return True
    if "qwen" in value and "3.5" in value:
        return True
    from .model_families import is_gemma4_filename

    if is_gemma4_filename(value):
        return True
    return False


# ---------------------------------------------------------------------------
# Settings normalization
# ---------------------------------------------------------------------------


def _coerce_float_setting(raw_value: Any, *, field: str, default: float) -> float:
    value = default if raw_value is None else raw_value
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ModelSettingsValidationError(field) from exc


def _coerce_int_setting(raw_value: Any, *, field: str, default: int) -> int:
    value = default if raw_value is None else raw_value
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ModelSettingsValidationError(field) from exc


def _normalize_chat_settings(raw_value: Any) -> dict[str, Any]:
    raw = raw_value if isinstance(raw_value, dict) else {}
    return {
        "temperature": _coerce_float_setting(
            raw.get("temperature"),
            field="chat.temperature",
            default=DEFAULT_MODEL_CHAT_SETTINGS["temperature"],
        ),
        "top_p": _coerce_float_setting(
            raw.get("top_p"),
            field="chat.top_p",
            default=DEFAULT_MODEL_CHAT_SETTINGS["top_p"],
        ),
        "top_k": _coerce_int_setting(
            raw.get("top_k"),
            field="chat.top_k",
            default=DEFAULT_MODEL_CHAT_SETTINGS["top_k"],
        ),
        "repetition_penalty": _coerce_float_setting(
            raw.get("repetition_penalty"),
            field="chat.repetition_penalty",
            default=DEFAULT_MODEL_CHAT_SETTINGS["repetition_penalty"],
        ),
        "presence_penalty": _coerce_float_setting(
            raw.get("presence_penalty"),
            field="chat.presence_penalty",
            default=DEFAULT_MODEL_CHAT_SETTINGS["presence_penalty"],
        ),
        "max_tokens": _coerce_int_setting(
            raw.get("max_tokens"),
            field="chat.max_tokens",
            default=DEFAULT_MODEL_CHAT_SETTINGS["max_tokens"],
        ),
        "stream": bool(raw.get("stream", DEFAULT_MODEL_CHAT_SETTINGS["stream"])),
        "generation_mode": (
            "deterministic"
            if str(raw.get("generation_mode", DEFAULT_MODEL_CHAT_SETTINGS["generation_mode"])).strip().lower() == "deterministic"
            else "random"
        ),
        "seed": _coerce_int_setting(
            raw.get("seed"),
            field="chat.seed",
            default=DEFAULT_MODEL_CHAT_SETTINGS["seed"],
        ),
        "system_prompt": str(raw.get("system_prompt", DEFAULT_MODEL_CHAT_SETTINGS["system_prompt"]) or ""),
        "cache_prompt": bool(raw.get("cache_prompt", DEFAULT_MODEL_CHAT_SETTINGS["cache_prompt"])),
    }


def _normalize_vision_settings(raw_value: Any, *, filename: str) -> dict[str, Any]:
    raw = raw_value if isinstance(raw_value, dict) else {}
    default_enabled = model_supports_vision_filename(filename)
    projector_filename_raw = raw.get("projector_filename")
    projector_filename = None
    if projector_filename_raw is not None:
        value = str(projector_filename_raw).strip()
        projector_filename = value or None
    projector_mode = str(raw.get("projector_mode", DEFAULT_MODEL_VISION_SETTINGS["projector_mode"]) or "default").strip().lower()
    if projector_mode not in {"default", "custom"}:
        projector_mode = "default"
    return {
        "enabled": bool(raw.get("enabled", default_enabled)),
        "projector_mode": projector_mode,
        "projector_filename": projector_filename,
    }


def normalize_model_settings(raw_value: Any, *, filename: str) -> dict[str, Any]:
    raw = raw_value if isinstance(raw_value, dict) else {}
    return {
        "chat": _normalize_chat_settings(raw.get("chat")),
        "vision": _normalize_vision_settings(raw.get("vision"), filename=filename),
    }


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


def build_model_capabilities(filename: str | None) -> dict[str, Any]:
    return {
        "vision": model_supports_vision_filename(filename),
    }


def apply_model_chat_defaults(payload: dict[str, Any], *, active_model_filename: str | None) -> dict[str, Any]:
    if not is_qwen35_a3b_filename(active_model_filename):
        return payload

    chat_template_kwargs = payload.get("chat_template_kwargs")
    if isinstance(chat_template_kwargs, dict) and "enable_thinking" in chat_template_kwargs:
        return payload

    updated = dict(payload)
    if isinstance(chat_template_kwargs, dict):
        merged = dict(chat_template_kwargs)
    else:
        merged = {}
    merged["enable_thinking"] = False
    updated["chat_template_kwargs"] = merged
    return updated


# ---------------------------------------------------------------------------
# Registry queries (pure)
# ---------------------------------------------------------------------------


def get_model_by_id(state: dict[str, Any], model_id: str) -> dict[str, Any] | None:
    for item in state.get("models", []):
        if isinstance(item, dict) and item.get("id") == model_id:
            return item
    return None


def _is_discoverable_local_model_filename(filename: str) -> bool:
    name = _sanitize_filename(filename)
    if not _has_valid_model_extension(name):
        return False
    stem = Path(name).stem.lower()
    if stem.startswith("mmproj") or "mmproj" in stem:
        return False
    return True


# ---------------------------------------------------------------------------
# Atomic write utility
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        import tempfile

        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload))
        os.replace(tmp_name, path)
    except OSError:
        logger.warning("Could not persist JSON state to %s", path, exc_info=True)


# ---------------------------------------------------------------------------
# File / path operations
# ---------------------------------------------------------------------------


def model_file_path(models_dir: Path, filename: str) -> Path:
    return models_dir / filename


def model_file_present(models_dir: Path, filename: str) -> bool:
    path = model_file_path(models_dir, filename)
    try:
        return path.exists() and path.stat().st_size > 0
    except OSError:
        return False


def describe_model_storage(models_dir: Path, filename: str) -> dict[str, Any]:
    path = model_file_path(models_dir, filename)
    size_bytes = 0
    exists = False

    try:
        exists = path.exists()
    except OSError:
        exists = False

    if exists:
        try:
            size_bytes = max(0, int(path.stat().st_size))
        except OSError:
            size_bytes = 0

    return {
        "location": "local",
        "size_bytes": size_bytes,
        "exists": exists,
    }


def resolve_model_runtime_path(models_dir: Path, filename: str) -> Path:
    """Return the real filesystem path for a model, resolving symlinks."""
    path = model_file_path(models_dir, filename)
    try:
        if path.is_symlink():
            return path.resolve(strict=False)
    except OSError:
        return path
    return path


def discover_local_model_filenames(models_dir: Path) -> list[str]:
    try:
        children = list(models_dir.iterdir())
    except OSError:
        return []
    names: list[str] = []
    for child in children:
        if not child.is_file():
            continue
        filename = _sanitize_filename(child.name)
        if not _is_discoverable_local_model_filename(filename):
            continue
        names.append(filename)
    return sorted(set(names))


# ---------------------------------------------------------------------------
# Default model record (built from ModelStoreConfig)
# ---------------------------------------------------------------------------


def _default_model_record(store: ModelStoreConfig) -> dict[str, Any]:
    return {
        "id": "default",
        "filename": store.default_filename,
        "source_url": store.default_url,
        "source_type": "url",
        "status": "not_downloaded",
        "error": None,
        "settings": normalize_model_settings(None, filename=store.default_filename),
    }


# ---------------------------------------------------------------------------
# State normalization and persistence
# ---------------------------------------------------------------------------


def _normalize_models_state(store: ModelStoreConfig, raw: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = raw or {}
    models_raw = payload.get("models")
    models: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_filenames: set[str] = set()

    if isinstance(models_raw, list):
        for item in models_raw:
            if not isinstance(item, dict):
                continue
            source_url = str(item.get("source_url") or "")
            filename = _sanitize_filename(str(item.get("filename") or ""))
            if not _has_valid_model_extension(filename):
                filename = f"{Path(filename).stem}.gguf"
            item_id_raw = str(item.get("id") or _slugify_id(Path(filename).stem))
            item_id = _unique_model_id(_slugify_id(item_id_raw), seen_ids)
            filename = _unique_filename(filename, seen_filenames)
            seen_ids.add(item_id)
            seen_filenames.add(filename)
            source_type_raw = str(item.get("source_type") or "").strip().lower()
            if source_url:
                source_type = source_type_raw or "url"
            elif source_type_raw in {"upload", "local_file"}:
                source_type = source_type_raw
            else:
                source_type = "upload"
            models.append(
                {
                    "id": item_id,
                    "filename": filename,
                    "source_url": source_url or None,
                    "source_type": source_type,
                    "status": str(item.get("status") or "not_downloaded"),
                    "error": item.get("error"),
                    "settings": normalize_model_settings(item.get("settings"), filename=filename),
                }
            )

    if not models:
        default_model = _default_model_record(store)
        models.append(default_model)
        seen_ids.add(default_model["id"])
        seen_filenames.add(default_model["filename"])
    elif "default" not in seen_ids:
        default_model = _default_model_record(store)
        default_model["id"] = _unique_model_id("default", seen_ids)
        default_model["filename"] = _unique_filename(default_model["filename"], seen_filenames)
        models.insert(0, default_model)
        seen_ids.add(default_model["id"])
        seen_filenames.add(default_model["filename"])

    for local_filename in discover_local_model_filenames(store.models_dir):
        if local_filename in seen_filenames:
            continue
        local_id = _unique_model_id(_slugify_id(Path(local_filename).stem), seen_ids)
        models.append(
            {
                "id": local_id,
                "filename": local_filename,
                "source_url": None,
                "source_type": "local_file",
                "status": "ready",
                "error": None,
                "settings": normalize_model_settings(None, filename=local_filename),
            }
        )
        seen_ids.add(local_id)
        seen_filenames.add(local_filename)

    runtime_model_name = _sanitize_filename(store.current_model_filename) if store.current_model_filename else ""
    active_model_id = str(payload.get("active_model_id") or "").strip()
    if active_model_id not in seen_ids:
        runtime_match = next(
            (
                str(item.get("id") or "")
                for item in models
                if isinstance(item, dict) and _sanitize_filename(str(item.get("filename") or "")) == runtime_model_name
            ),
            "",
        )
        active_model_id = runtime_match or models[0]["id"]

    default_model_id = str(payload.get("default_model_id") or "default")
    if default_model_id not in seen_ids:
        default_model_id = "default" if "default" in seen_ids else models[0]["id"]

    current_download_model_id = payload.get("current_download_model_id")
    if current_download_model_id not in seen_ids:
        current_download_model_id = None

    return {
        "version": MODELS_STATE_VERSION,
        "countdown_enabled": bool(payload.get("countdown_enabled", True)),
        "default_model_downloaded_once": bool(payload.get("default_model_downloaded_once", False)),
        "active_model_id": active_model_id,
        "default_model_id": default_model_id,
        "current_download_model_id": current_download_model_id,
        "models": models,
    }


def ensure_models_state(store: ModelStoreConfig) -> dict[str, Any]:
    raw: dict[str, Any] | None = None
    if store.state_path.exists():
        try:
            loaded = json.loads(store.state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                raw = loaded
        except (OSError, json.JSONDecodeError):
            raw = None

    normalized = _normalize_models_state(store, raw)
    default_model_id = str(normalized.get("default_model_id") or "default")
    default_model = get_model_by_id(normalized, default_model_id)
    if isinstance(default_model, dict):
        default_filename = str(default_model.get("filename") or "")
        if default_filename in store.known_default_filenames and model_file_present(store.models_dir, default_filename):
            normalized["default_model_downloaded_once"] = True
    _atomic_write_json(store.state_path, normalized)
    return normalized


def save_models_state(store: ModelStoreConfig, state: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_models_state(store, state)
    _atomic_write_json(store.state_path, normalized)
    return normalized


# ---------------------------------------------------------------------------
# Registry mutations
# ---------------------------------------------------------------------------


def update_model_settings(
    store: ModelStoreConfig,
    *,
    model_id: str,
    settings: dict[str, Any],
) -> tuple[bool, str, dict[str, Any] | None]:
    state = ensure_models_state(store)
    model = get_model_by_id(state, model_id)
    if model is None:
        return False, "model_not_found", None
    filename = str(model.get("filename") or "")
    try:
        model["settings"] = normalize_model_settings(settings, filename=filename)
    except ModelSettingsValidationError:
        return False, "invalid_settings", None
    saved = save_models_state(store, state)
    updated = get_model_by_id(saved, model_id)
    return True, "updated", updated


def register_model_url(store: ModelStoreConfig, source_url: str, alias: str | None = None) -> tuple[bool, str, dict[str, Any] | None]:
    ok, reason, filename = validate_model_url(source_url)
    if not ok:
        return False, reason, None

    state = ensure_models_state(store)
    models = state.get("models", [])
    assert isinstance(models, list)
    existing_ids = {str(item.get("id")) for item in models if isinstance(item, dict)}
    existing_names = {str(item.get("filename")) for item in models if isinstance(item, dict)}

    for item in models:
        if isinstance(item, dict) and str(item.get("source_url") or "") == source_url:
            saved = save_models_state(store, state)
            model = get_model_by_id(saved, str(item.get("id") or ""))
            return True, "already_exists", model

    preferred_name = filename
    if alias:
        alias_safe = _sanitize_filename(alias)
        if not alias_safe.lower().endswith(".gguf"):
            alias_safe = f"{Path(alias_safe).stem}.gguf"
        if alias_safe:
            preferred_name = alias_safe

    final_name = _unique_filename(preferred_name, existing_names)
    model_id = _unique_model_id(_slugify_id(Path(final_name).stem), existing_ids)
    model_record = {
        "id": model_id,
        "filename": final_name,
        "source_url": source_url,
        "source_type": "url",
        "status": "ready" if model_file_present(store.models_dir, final_name) else "not_downloaded",
        "error": None,
    }
    models.append(model_record)
    saved = save_models_state(store, state)
    created = get_model_by_id(saved, model_id)
    return True, "registered", created


def delete_model(store: ModelStoreConfig, *, model_id: str) -> tuple[bool, str, bool, int, bool]:
    state = ensure_models_state(store)
    active_model_id = str(state.get("active_model_id") or "")
    target = get_model_by_id(state, model_id)
    if target is None:
        return False, "model_not_found", False, 0, False
    was_active = model_id == active_model_id

    filename = str(target.get("filename") or "")
    models = state.get("models", [])
    assert isinstance(models, list)

    same_filename_elsewhere = any(
        isinstance(item, dict)
        and str(item.get("id") or "") != model_id
        and str(item.get("filename") or "") == filename
        for item in models
    )

    deleted_file = False
    freed_bytes = 0
    if filename and not same_filename_elsewhere:
        candidate_paths = (
            model_file_path(store.models_dir, filename),
            model_file_path(store.models_dir, filename + ".part"),
        )
        for candidate_path in candidate_paths:
            candidate_is_symlink = False
            try:
                candidate_is_symlink = candidate_path.is_symlink()
            except OSError:
                candidate_is_symlink = False
            if not candidate_path.exists() and not candidate_is_symlink:
                continue

            target_path: Path | None = None
            file_size = 0
            if candidate_is_symlink:
                try:
                    target_path = candidate_path.resolve(strict=False)
                    if target_path.exists():
                        file_size = max(0, target_path.stat().st_size)
                except OSError:
                    target_path = None
                    file_size = 0
            else:
                try:
                    file_size = max(0, candidate_path.stat().st_size)
                except OSError:
                    file_size = 0
            try:
                candidate_path.unlink(missing_ok=True)
                if target_path is not None and target_path.exists():
                    target_path.unlink(missing_ok=True)
                deleted_file = True
                freed_bytes += file_size
            except OSError:
                logger.warning("Could not delete model file: %s", candidate_path, exc_info=True)
                return False, "delete_failed", False, 0, was_active

    remaining_models = [
        item
        for item in models
        if not (isinstance(item, dict) and str(item.get("id") or "") == model_id)
    ]
    state["models"] = remaining_models
    if str(state.get("current_download_model_id") or "") == model_id:
        state["current_download_model_id"] = None
    if was_active:
        next_active_id: str | None = None
        for item in remaining_models:
            if not isinstance(item, dict):
                continue
            candidate_id = str(item.get("id") or "")
            candidate_name = str(item.get("filename") or "")
            if candidate_id and model_file_present(store.models_dir, candidate_name):
                next_active_id = candidate_id
                break
        if next_active_id is None:
            for item in remaining_models:
                if isinstance(item, dict) and item.get("id"):
                    next_active_id = str(item["id"])
                    break
        if next_active_id is None:
            next_active_id = str(state.get("default_model_id") or "default")
        state["active_model_id"] = next_active_id
    save_models_state(store, state)
    return True, "deleted", deleted_file, freed_bytes, was_active


def any_model_ready(store: ModelStoreConfig) -> bool:
    """Return True if any model in the models state has a file on disk."""
    state = ensure_models_state(store)
    models = state.get("models") or []
    for model in models:
        filename = str(model.get("filename") or "").strip()
        if filename and model_file_present(store.models_dir, filename):
            return True
    return False


# ---------------------------------------------------------------------------
# Projector download
# ---------------------------------------------------------------------------


def download_default_projector_for_model(store: ModelStoreConfig, model_id: str) -> tuple[bool, str, str | None]:
    """Download the default vision projector for a model from HuggingFace."""
    import httpx

    from .model_families import default_projector_candidates_for_model, projector_repo_for_model

    state = ensure_models_state(store)
    model = get_model_by_id(state, model_id)
    if model is None:
        return False, "model_not_found", None
    filename = str(model.get("filename") or "")
    if not model_supports_vision_filename(filename):
        return False, "vision_not_supported", None
    repo = projector_repo_for_model(filename, source_url=model.get("source_url"))
    candidates = default_projector_candidates_for_model(filename)
    if not repo or not candidates:
        return False, "projector_repo_unknown", None

    models_dir = store.models_dir
    models_dir.mkdir(parents=True, exist_ok=True)

    _generics = {"mmproj-F16.gguf", "mmproj-bf16.gguf"}
    preferred_local: str | None = None
    for c in candidates:
        if c == "mmproj-F16.gguf":
            break
        preferred_local = c
    preferred_local_bf16: str | None = None
    if preferred_local:
        preferred_local_bf16 = preferred_local.replace("-f16.gguf", "-bf16.gguf")

    for candidate in candidates:
        if candidate in _generics and preferred_local:
            continue
        target_path = models_dir / candidate
        if target_path.exists():
            return True, "downloaded", candidate

    download_targets = list(candidates)
    if "mmproj-bf16.gguf" not in download_targets:
        download_targets.append("mmproj-bf16.gguf")

    client = httpx.Client(follow_redirects=True, timeout=120.0)
    try:
        for candidate in download_targets:
            url = f"https://huggingface.co/{repo}/resolve/main/{candidate}"
            if candidate == "mmproj-F16.gguf" and preferred_local:
                local_name = preferred_local
            elif candidate == "mmproj-bf16.gguf" and preferred_local_bf16:
                local_name = preferred_local_bf16
            else:
                local_name = candidate
            target_path = models_dir / local_name
            if target_path.exists():
                return True, "downloaded", local_name
            part_path = target_path.with_suffix(target_path.suffix + ".part")
            try:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with part_path.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            if chunk:
                                handle.write(chunk)
                part_path.replace(target_path)
                if local_name not in _generics:
                    for g in _generics:
                        (models_dir / g).unlink(missing_ok=True)
                return True, "downloaded", local_name
            except Exception:
                part_path.unlink(missing_ok=True)
                continue
    finally:
        client.close()
    return False, "download_failed", None
