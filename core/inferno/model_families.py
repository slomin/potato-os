from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

QWEN35_PROJECTOR_REPO_RULES: Final[tuple[tuple[tuple[str, ...], str], ...]] = (
    (("35b", "a3b", "hauhaucs"), "HauhauCS/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive"),
    (("35b", "a3b"), "AesSedai/Qwen3.5-35B-A3B-GGUF"),
    (("9b", "byteshape"), "byteshape/Qwen3.5-9B-GGUF"),
    (("9b",), "unsloth/Qwen3.5-9B-GGUF"),
    (("4b", "hauhaucs"), "HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive"),
    (("4b",), "unsloth/Qwen3.5-4B-GGUF"),
    (("2b",), "unsloth/Qwen3.5-2B-GGUF"),
    (("0.8b",), "unsloth/Qwen3.5-0.8B-GGUF"),
)


def _normalized_model_name(filename: str | None) -> str:
    return str(filename or "").strip().lower()


def is_qwen35_filename(filename: str | None) -> bool:
    model_name = _normalized_model_name(filename)
    return bool(model_name) and "qwen" in model_name and "3.5" in model_name


def _token_at_boundary(token: str, text: str) -> bool:
    """Match token only when surrounded by non-alphanumeric boundaries.

    Prevents substring collisions like '9b' matching inside '19b'
    or '2b' matching inside '3.92bpw'.
    """
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", text))


def _qwen35_projector_repo(filename: str | None, source_url: str | None = None) -> str | None:
    model_name = _normalized_model_name(filename)
    if not is_qwen35_filename(model_name):
        return None

    # Match tokens against filename + source URL so publisher-specific rules
    # fire even when the filename itself doesn't contain the publisher name.
    match_text = model_name
    if source_url:
        match_text = _normalized_model_name(source_url) + " " + match_text

    for required_tokens, repo in QWEN35_PROJECTOR_REPO_RULES:
        if all(_token_at_boundary(token, match_text) for token in required_tokens):
            return repo
    return None


GEMMA4_PROJECTOR_REPO_RULES: Final[tuple[tuple[tuple[str, ...], str], ...]] = (
    (("e2b",), "unsloth/gemma-4-E2B-it-GGUF"),
    (("e4b",), "unsloth/gemma-4-E4B-it-GGUF"),
    (("26b", "a4b"), "unsloth/gemma-4-26B-A4B-it-GGUF"),
)


def is_gemma4_filename(filename: str | None) -> bool:
    model_name = _normalized_model_name(filename)
    return bool(model_name) and "gemma" in model_name and _token_at_boundary("4", model_name)


def _gemma4_projector_repo(filename: str | None, source_url: str | None = None) -> str | None:
    model_name = _normalized_model_name(filename)
    if not is_gemma4_filename(model_name):
        return None

    match_text = model_name
    if source_url:
        match_text = _normalized_model_name(source_url) + " " + match_text

    for required_tokens, repo in GEMMA4_PROJECTOR_REPO_RULES:
        if all(_token_at_boundary(token, match_text) for token in required_tokens):
            return repo
    return None


def _is_gemma4_26b_a4b(filename: str | None) -> bool:
    model_name = _normalized_model_name(filename)
    return is_gemma4_filename(model_name) and "26b" in model_name and "a4b" in model_name


def recommended_runtime_for_model(filename: str | None) -> str | None:
    """Return the preferred runtime family for a model, or None for no preference."""
    if filename and _normalized_model_name(filename).endswith(".litertlm"):
        return "litert"
    if _is_gemma4_26b_a4b(filename):
        return "ik_llama"
    return None


def projector_repo_for_model(filename: str | None, source_url: str | None = None) -> str | None:
    return (
        _qwen35_projector_repo(filename, source_url=source_url)
        or _gemma4_projector_repo(filename, source_url=source_url)
    )


# ---------------------------------------------------------------------------
# Vision family detection & projector candidates
# ---------------------------------------------------------------------------


def _is_vision_family(filename: str) -> bool:
    """Return True if the filename belongs to a curated vision model family."""
    model_name = filename.strip().lower()
    if "qwen" in model_name and "3.5" in model_name:
        return True
    return is_gemma4_filename(model_name)


def default_projector_candidates_for_model(filename: str | None) -> list[str]:
    """Return ordered list of mmproj filename candidates for a given model."""
    model_name = str(filename or "").strip()
    if not model_name or not _is_vision_family(model_name):
        return []

    stem = Path(model_name).stem
    stem_candidates = [stem]
    trimmed_stem = stem
    while True:
        next_stem = re.sub(
            r"-(?:UD-)?(?:\d+(?:\.\d+)?bpw|I?Q\d+(?:_[A-Za-z0-9]+)*|MXFP\d+_MOE)$",
            "",
            trimmed_stem,
            flags=re.IGNORECASE,
        )
        if next_stem == trimmed_stem or not next_stem:
            break
        trimmed_stem = next_stem
        if trimmed_stem not in stem_candidates:
            stem_candidates.append(trimmed_stem)

    candidates: list[str] = []
    # Model-specific candidates first (f16 preferred, bf16 fallback),
    # then generic F16 last. This ensures a downloaded model-specific
    # bf16 projector is found before a stale generic F16.
    for precision in ("f16", "bf16"):
        for candidate_stem in stem_candidates:
            candidate_name = f"mmproj-{candidate_stem}-{precision}.gguf"
            if candidate_name not in candidates:
                candidates.append(candidate_name)
    if "mmproj-F16.gguf" not in candidates:
        candidates.append("mmproj-F16.gguf")
    return candidates


def build_model_projector_status(models_dir: Path, model: dict[str, Any]) -> dict[str, Any]:
    """Build projector status for a model (presence, path, candidates)."""
    from .model_registry import normalize_model_settings

    filename = str(model.get("filename") or "")
    settings = normalize_model_settings(model.get("settings"), filename=filename)
    vision = settings.get("vision", {})
    projector_mode = str(vision.get("projector_mode") or "default").strip().lower()
    configured_filename = str(vision.get("projector_filename") or "").strip() or None
    default_candidates = default_projector_candidates_for_model(filename)
    search_names: list[str] = []
    if projector_mode == "custom":
        if configured_filename:
            search_names.append(configured_filename)
    else:
        for candidate in default_candidates:
            if candidate not in search_names:
                search_names.append(candidate)
        if configured_filename and configured_filename not in search_names:
            search_names.append(configured_filename)

    resolved_name = configured_filename
    present = False
    resolved_path = None
    for candidate in search_names:
        candidate_path = models_dir / candidate
        if candidate_path.exists():
            present = True
            resolved_name = candidate
            resolved_path = candidate_path
            break

    return {
        "configured_filename": configured_filename,
        "filename": resolved_name,
        "present": present,
        "path": str(resolved_path) if resolved_path is not None else None,
        "default_candidates": default_candidates,
    }
