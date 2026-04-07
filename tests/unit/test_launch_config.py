"""Unit tests for core.inferno.launch_config — llama-server CLI arg builder."""

from __future__ import annotations

import pytest

from core.inferno.launch_config import build_llama_server_args


# ---------------------------------------------------------------------------
# Basic arg construction
# ---------------------------------------------------------------------------


def test_basic_args_include_all_mandatory_flags():
    args = build_llama_server_args(
        llama_server_bin="/opt/potato/llama/bin/llama-server",
        model_path="/opt/potato/models/Qwen3.5-2B-Q4_K_M.gguf",
        slot_save_path="/opt/potato/state/llama-slots",
    )
    assert args[0] == "/opt/potato/llama/bin/llama-server"
    assert "--model" in args
    assert "/opt/potato/models/Qwen3.5-2B-Q4_K_M.gguf" in args
    assert "--host" in args
    assert "--port" in args
    assert "--ctx-size" in args
    assert "--cache-ram" in args
    assert "--parallel" in args
    assert "--slot-save-path" in args


def test_defaults_match_shell_script_defaults():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
    )
    idx = args.index
    assert args[idx("--host") + 1] == "0.0.0.0"
    assert args[idx("--port") + 1] == "8080"
    assert args[idx("--ctx-size") + 1] == "16384"
    assert args[idx("--cache-ram") + 1] == "1024"
    assert args[idx("--parallel") + 1] == "1"


# ---------------------------------------------------------------------------
# Vision projector (mmproj)
# ---------------------------------------------------------------------------


def test_mmproj_path_adds_flag():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        mmproj_path="/models/mmproj-F16.gguf",
    )
    assert "--mmproj" in args
    assert "/models/mmproj-F16.gguf" in args


def test_no_mmproj_omits_flag():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
    )
    assert "--mmproj" not in args


# ---------------------------------------------------------------------------
# KV cache configuration
# ---------------------------------------------------------------------------


def test_kv_cache_defaults():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
    )
    assert "--cache-type-k" in args
    assert "--cache-type-v" in args
    idx = args.index
    assert args[idx("--cache-type-k") + 1] == "q8_0"
    assert args[idx("--cache-type-v") + 1] == "q8_0"


def test_custom_kv_flags_override_defaults():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        kv_flags="--cache-type-k f16 --cache-type-v f16",
    )
    assert "--cache-type-k" in args
    assert "f16" in args
    # Should NOT have the default q8_0 values
    assert "q8_0" not in args


# ---------------------------------------------------------------------------
# Feature toggles
# ---------------------------------------------------------------------------


def test_flash_attn_enabled():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        flash_attn=True,
    )
    assert "--flash-attn" in args
    assert args[args.index("--flash-attn") + 1] == "on"


def test_flash_attn_disabled():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        flash_attn=False,
    )
    assert "--flash-attn" not in args


def test_jinja_enabled():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        jinja=True,
    )
    assert "--jinja" in args


def test_jinja_disabled():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        jinja=False,
    )
    assert "--jinja" not in args


def test_no_warmup_enabled():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        no_warmup=True,
    )
    assert "--no-warmup" in args


def test_no_warmup_disabled():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        no_warmup=False,
    )
    assert "--no-warmup" not in args


def test_no_mmap_enabled():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        no_mmap=True,
    )
    assert "--no-mmap" in args


def test_no_mmap_disabled():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        no_mmap=False,
    )
    assert "--no-mmap" not in args


# ---------------------------------------------------------------------------
# Reasoning and chat template
# ---------------------------------------------------------------------------


def test_reasoning_format_default():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
    )
    assert "--reasoning-format" in args
    assert args[args.index("--reasoning-format") + 1] == "none"


def test_reasoning_format_custom():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        reasoning_format="deepseek",
    )
    assert args[args.index("--reasoning-format") + 1] == "deepseek"


def test_chat_template_kwargs_default():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
    )
    assert "--chat-template-kwargs" in args
    assert '{"enable_thinking": false}' in args


def test_chat_template_kwargs_custom():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        chat_template_kwargs='{"enable_thinking": true}',
    )
    assert args[args.index("--chat-template-kwargs") + 1] == '{"enable_thinking": true}'


# ---------------------------------------------------------------------------
# Runtime family — WebUI suppression
# ---------------------------------------------------------------------------


def test_ik_llama_uses_webui_none():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        runtime_family="ik_llama",
    )
    assert "--webui" in args
    assert args[args.index("--webui") + 1] == "none"
    assert "--no-webui" not in args


def test_llama_cpp_uses_no_webui():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        runtime_family="llama_cpp",
    )
    assert "--no-webui" in args
    assert "--webui" not in args or args[args.index("--webui") + 1] != "none"


def test_unknown_family_no_webui_flag():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        runtime_family=None,
    )
    assert "--webui" not in args
    assert "--no-webui" not in args


# ---------------------------------------------------------------------------
# Extra flags passthrough
# ---------------------------------------------------------------------------


def test_extra_flags_split_and_appended():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        extra_flags="--verbose --log-timestamps",
    )
    assert "--verbose" in args
    assert "--log-timestamps" in args


def test_empty_extra_flags_ignored():
    args = build_llama_server_args(
        llama_server_bin="/bin/llama-server",
        model_path="/model.gguf",
        slot_save_path="/slots",
        extra_flags="",
    )
    # Should not crash or add empty strings
    assert "" not in args[1:]  # first element is the binary path
