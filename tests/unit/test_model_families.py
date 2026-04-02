from __future__ import annotations

import pytest

from core.constants.model_families import projector_repo_for_model


def test_projector_repo_for_qwen35_9b():
    """Qwen3.5-9B generic model resolves to unsloth 9B projector repo."""
    assert projector_repo_for_model("Qwen3.5-9B-Q4_K_S-3.92bpw.gguf") == "unsloth/Qwen3.5-9B-GGUF"


def test_projector_repo_for_qwen35_9b_byteshape_by_filename():
    """ByteShape in filename resolves to ByteShape repo."""
    assert projector_repo_for_model("byteshape-Qwen3.5-9B-Q4_K_S.gguf") == "byteshape/Qwen3.5-9B-GGUF"


def test_projector_repo_for_qwen35_9b_byteshape_by_source_url():
    """ByteShape in source_url resolves to ByteShape repo even when filename
    has no publisher prefix — this is the real HuggingFace scenario."""
    assert projector_repo_for_model(
        "Qwen3.5-9B-Q4_K_S-3.92bpw.gguf",
        source_url="https://huggingface.co/byteshape/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_S-3.92bpw.gguf",
    ) == "byteshape/Qwen3.5-9B-GGUF"


def test_projector_repo_for_qwen35_9b_without_source_url():
    """Generic 9B without source_url falls back to unsloth."""
    assert projector_repo_for_model("Qwen3.5-9B-Q4_K_S-3.92bpw.gguf") == "unsloth/Qwen3.5-9B-GGUF"


def test_projector_repo_returns_none_for_unknown_qwen35_size():
    """Unrecognized Qwen3.5 sizes must return None, not silently fall back."""
    assert projector_repo_for_model("Qwen3.5-7B-Q4_K_M.gguf") is None


def test_projector_repo_no_substring_collision_19b():
    """19B must NOT match the 9B rule — '9b' is a substring of '19b'."""
    assert projector_repo_for_model("Qwen3.5-Creative-19B-A3B-REAP.Q4_K_S.gguf") is None


def test_projector_repo_no_substring_collision_bpw():
    """3.92bpw must NOT match the 2B rule — '2b' is a substring of '3.92bpw'."""
    result = projector_repo_for_model("Qwen3.5-9B-Q4_K_S-3.92bpw.gguf")
    assert result == "unsloth/Qwen3.5-9B-GGUF", f"got {result!r} (2B collision via '3.92bpw')"


def test_projector_repo_dot_delimited_9b():
    """Dot-delimited filenames like Qwen3.5-9B.gguf must still match."""
    assert projector_repo_for_model("Qwen3.5-9B.gguf") == "unsloth/Qwen3.5-9B-GGUF"
    assert projector_repo_for_model("Qwen3.5-9B.Q4_K_S.gguf") == "unsloth/Qwen3.5-9B-GGUF"


def test_projector_repo_dot_delimited_4b():
    """Dot-delimited filenames like Qwen3.5-4B.Q4_K_M.gguf must still match."""
    assert projector_repo_for_model("Qwen3.5-4B.Q4_K_M.gguf") == "unsloth/Qwen3.5-4B-GGUF"


def test_default_candidates_include_model_specific_bf16_but_not_generic():
    """default_projector_candidates_for_model must include model-specific bf16
    names but NOT generic mmproj-bf16.gguf (unsafe cross-model reuse)."""
    from core.model_state import default_projector_candidates_for_model

    candidates = default_projector_candidates_for_model("Qwen3.5-9B-Q4_K_S.gguf")
    assert "mmproj-F16.gguf" in candidates
    assert "mmproj-Qwen3.5-9B-f16.gguf" in candidates
    assert "mmproj-Qwen3.5-9B-bf16.gguf" in candidates
    # Generic bf16 must NOT be in the list — it's unsafe for cross-model reuse
    assert "mmproj-bf16.gguf" not in candidates


def test_projector_status_finds_model_specific_bf16_on_disk(runtime):
    """build_model_projector_status must detect a model-specific bf16 projector."""
    from core.model_state import build_model_projector_status

    models_dir = runtime.base_dir / "models"
    (models_dir / "mmproj-Qwen3.5-9B-bf16.gguf").write_bytes(b"bf16-projector")

    model = {
        "filename": "Qwen3.5-9B-Q4_K_S.gguf",
        "settings": {
            "vision": {"enabled": True, "projector_mode": "default", "projector_filename": None},
        },
    }
    status = build_model_projector_status(runtime, model)
    assert status["present"] is True
    assert "bf16" in status["filename"]


def test_projector_status_ignores_stale_generic_bf16_for_wrong_model(runtime):
    """A generic mmproj-bf16.gguf left over from a 9B download must NOT be
    reported as present for a 4B model — wrong dimensions would crash. #136."""
    from core.model_state import build_model_projector_status

    models_dir = runtime.base_dir / "models"
    (models_dir / "mmproj-bf16.gguf").write_bytes(b"stale-9b-bf16")

    model = {
        "filename": "Qwen3.5-4B-Q4_K_M.gguf",
        "settings": {
            "vision": {"enabled": True, "projector_mode": "default", "projector_filename": None},
        },
    }
    status = build_model_projector_status(runtime, model)
    assert status["present"] is False, (
        "Generic mmproj-bf16.gguf must not be accepted for a different model size"
    )


@pytest.mark.parametrize(
    "filename, expected_repo",
    [
        ("Qwen3.5-2B-Q4_K_M.gguf", "unsloth/Qwen3.5-2B-GGUF"),
        ("Qwen3.5-4B-Q4_K_M.gguf", "unsloth/Qwen3.5-4B-GGUF"),
        ("Qwen3.5-0.8B-Q4_K_M.gguf", "unsloth/Qwen3.5-0.8B-GGUF"),
        ("Qwen3.5-35B-A3B-Q2_K_L.gguf", "AesSedai/Qwen3.5-35B-A3B-GGUF"),
    ],
)
def test_projector_repo_existing_sizes_unchanged(filename: str, expected_repo: str):
    """Existing size mappings must not regress."""
    assert projector_repo_for_model(filename) == expected_repo
