"""Llama-server launch configuration builder.

Assembles the complete CLI argument list for llama-server from
pre-computed configuration values.  Pure function — no file I/O,
no environment variable reads, no imports from Potato product code.
"""

from __future__ import annotations

from pathlib import Path


def build_llama_server_args(
    *,
    llama_server_bin: str | Path,
    model_path: str | Path,
    host: str = "0.0.0.0",
    port: int = 8080,
    ctx_size: int = 16384,
    parallel: int = 1,
    cache_ram_mib: int = 1024,
    slot_save_path: str | Path,
    mmproj_path: str | Path | None = None,
    cache_type_k: str = "q8_0",
    cache_type_v: str = "q8_0",
    kv_flags: str | None = None,
    flash_attn: bool = True,
    jinja: bool = True,
    no_warmup: bool = True,
    no_mmap: bool = False,
    reasoning_format: str = "none",
    chat_template_kwargs: str = '{"enable_thinking": false}',
    runtime_family: str | None = None,
    extra_flags: str | None = None,
) -> list[str]:
    """Build the complete llama-server command-line argument list.

    All business decisions (vision, device tuning, runtime family) must be
    resolved by the caller before invoking this function.  This keeps the
    builder free of I/O and Potato-specific imports.
    """
    args: list[str] = [
        str(llama_server_bin),
        "--model", str(model_path),
        "--host", str(host),
        "--port", str(port),
        "--ctx-size", str(ctx_size),
        "--cache-ram", str(cache_ram_mib),
        "--parallel", str(parallel),
        "--slot-save-path", str(slot_save_path),
    ]

    # Vision projector ---------------------------------------------------
    if mmproj_path is not None:
        args.extend(["--mmproj", str(mmproj_path)])

    # KV cache -----------------------------------------------------------
    if kv_flags and kv_flags.strip():
        args.extend(kv_flags.strip().split())
    else:
        args.extend(["--cache-type-k", cache_type_k, "--cache-type-v", cache_type_v])

    # Feature toggles ----------------------------------------------------
    if jinja:
        args.append("--jinja")
    if flash_attn:
        args.extend(["--flash-attn", "on"])
    if no_warmup:
        args.append("--no-warmup")
    if no_mmap:
        args.append("--no-mmap")

    # Reasoning / chat template ------------------------------------------
    args.extend(["--reasoning-format", reasoning_format])
    args.extend(["--chat-template-kwargs", chat_template_kwargs])

    # Runtime-family-specific flags --------------------------------------
    if runtime_family == "ik_llama":
        args.extend(["--webui", "none"])
    elif runtime_family == "llama_cpp":
        args.append("--no-webui")

    # Admin extra flags --------------------------------------------------
    if extra_flags and extra_flags.strip():
        args.extend(extra_flags.strip().split())

    return args
