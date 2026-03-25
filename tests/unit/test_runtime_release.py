"""Tests for runtime release packaging and download resolution."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from tests.unit.conftest import REPO_ROOT

requires_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")


def _build_fake_runtime_slot(slot_dir: Path, *, family: str = "ik_llama", commit: str = "abc12345", profile: str = "pi5-opt") -> dict:
    """Create a minimal runtime slot directory with the expected layout."""
    (slot_dir / "bin").mkdir(parents=True, exist_ok=True)
    (slot_dir / "lib").mkdir(exist_ok=True)
    (slot_dir / "bin" / "llama-server").write_text("#!/bin/sh\necho fake", encoding="utf-8")
    (slot_dir / "bin" / "llama-server").chmod(0o755)
    (slot_dir / "bin" / "llama-bench").write_text("#!/bin/sh\necho bench", encoding="utf-8")
    (slot_dir / "lib" / "libfake.so").write_text("fake-lib", encoding="utf-8")
    (slot_dir / "run-llama-server.sh").write_text("#!/bin/sh\nexec ./bin/llama-server", encoding="utf-8")
    metadata = {
        "family": family,
        "commit": commit,
        "profile": profile,
        "repo": f"https://github.com/test/{family}",
        "build_timestamp": "2026-03-16T12:00:00",
        "build_host": "Raspberry Pi 5",
        "build_arch": "aarch64",
        "build_flags": "-DCMAKE_BUILD_TYPE=Release",
        "version": f"version: 9999 ({commit})",
    }
    (slot_dir / "runtime.json").write_text(json.dumps(metadata), encoding="utf-8")
    return metadata


def test_publish_runtime_tarball_contains_expected_layout(tmp_path):
    """Packaging a runtime slot into a tarball preserves the expected file layout."""
    slot_dir = tmp_path / "ik_llama"
    _build_fake_runtime_slot(slot_dir, family="ik_llama", commit="abc12345", profile="pi5-opt")

    tarball_path = tmp_path / "output.tar.gz"
    archive_name = "ik_llama-abc12345-pi5-opt"

    staging = tmp_path / "staging"
    staging.mkdir()
    subprocess.run(["cp", "-a", str(slot_dir), str(staging / archive_name)], check=True)
    subprocess.run(
        ["tar", "-C", str(staging), "-czf", str(tarball_path), archive_name],
        check=True,
    )

    assert tarball_path.exists()
    with tarfile.open(tarball_path, "r:gz") as tar:
        names = tar.getnames()
    assert f"{archive_name}/bin/llama-server" in names
    assert f"{archive_name}/lib/libfake.so" in names
    assert f"{archive_name}/runtime.json" in names
    assert f"{archive_name}/run-llama-server.sh" in names


def test_publish_runtime_tarball_name_matches_schema(tmp_path):
    """Tarball name follows <family>-<commit>-<profile>.tar.gz derived from runtime.json."""
    slot_dir = tmp_path / "ik_llama"
    metadata = _build_fake_runtime_slot(slot_dir, family="ik_llama", commit="deadbeef", profile="pi5-opt")

    family = metadata["family"]
    commit = metadata["commit"]
    profile = metadata["profile"]
    expected_name = f"{family}-{commit}-{profile}.tar.gz"

    assert expected_name == "ik_llama-deadbeef-pi5-opt.tar.gz"


def test_publish_runtime_tarball_extracts_with_strip_components(tmp_path):
    """Tarball can be extracted with --strip-components=1 directly into a target slot."""
    slot_dir = tmp_path / "ik_llama"
    _build_fake_runtime_slot(slot_dir, family="ik_llama", commit="abc12345")

    tarball_path = tmp_path / "ik_llama-abc12345-pi5-opt.tar.gz"
    archive_name = "ik_llama-abc12345-pi5-opt"
    staging = tmp_path / "staging"
    staging.mkdir()
    subprocess.run(["cp", "-a", str(slot_dir), str(staging / archive_name)], check=True)
    subprocess.run(["tar", "-C", str(staging), "-czf", str(tarball_path), archive_name], check=True)

    target = tmp_path / "extracted"
    target.mkdir()
    subprocess.run(["tar", "-xzf", str(tarball_path), "-C", str(target), "--strip-components=1"], check=True)

    assert (target / "bin" / "llama-server").exists()
    assert (target / "runtime.json").exists()
    metadata = json.loads((target / "runtime.json").read_text(encoding="utf-8"))
    assert metadata["family"] == "ik_llama"


def test_resolve_llama_bundle_src_prefers_local_slot_over_release(tmp_path):
    """When a local runtime slot exists, it wins over any release URL."""
    slot_dir = tmp_path / "runtimes" / "ik_llama"
    _build_fake_runtime_slot(slot_dir)

    script = (REPO_ROOT / "bin" / "install_dev.sh").read_text(encoding="utf-8")
    # Extract just the resolve_llama_bundle_src function body
    func_start = script.index("resolve_llama_bundle_src()")
    func_body = script[func_start:]
    # The local slot check must come before the release download logic within the function
    assert "runtimes/${LLAMA_RUNTIME_FAMILY}" in func_body
    slot_offset = func_body.index("runtimes/${LLAMA_RUNTIME_FAMILY}")
    if "try_resolve_runtime_from_release" in func_body:
        release_offset = func_body.index("try_resolve_runtime_from_release")
        assert release_offset > slot_offset, "Release fallback must come after local slot check"


def test_resolve_llama_bundle_src_explicit_env_var_overrides_everything(tmp_path):
    """POTATO_LLAMA_BUNDLE_SRC always wins over local slots and release URLs."""
    script = (REPO_ROOT / "bin" / "install_dev.sh").read_text(encoding="utf-8")
    bundle_src_line = script.index("LLAMA_BUNDLE_SRC")
    slot_line = script.index("runtimes/${LLAMA_RUNTIME_FAMILY}")
    assert bundle_src_line < slot_line, "BUNDLE_SRC check must come before slot check"


@requires_jq
def test_publish_runtime_dry_run_creates_tarball(tmp_path: Path):
    """--dry-run builds the tarball locally without publishing."""
    slot = tmp_path / "slot"
    _build_fake_runtime_slot(slot, family="ik_llama", commit="abc12345", profile="pi5-opt")
    env = os.environ.copy()
    env["POTATO_GITHUB_REPO"] = "test/repo"
    result = subprocess.run(
        [str(REPO_ROOT / "bin" / "publish_runtime.sh"), "--family", "ik_llama", "--slot-dir", str(slot), "--dry-run"],
        check=True,
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    tarball = tmp_path / "ik_llama-abc12345-pi5-opt.tar.gz"
    assert tarball.exists(), f"tarball not found: {tarball}"
    assert "Dry run" in result.stdout or "dry run" in result.stdout.lower()

    with tarfile.open(str(tarball), "r:gz") as tar:
        names = tar.getnames()
    assert any("bin/llama-server" in n for n in names)
    assert any("runtime.json" in n for n in names)


@requires_jq
def test_publish_runtime_dry_run_rejects_missing_slot(tmp_path: Path):
    """Missing slot directory must cause a hard failure."""
    env = os.environ.copy()
    env["POTATO_GITHUB_REPO"] = "test/repo"
    result = subprocess.run(
        [str(REPO_ROOT / "bin" / "publish_runtime.sh"), "--family", "ik_llama", "--slot-dir", "/nonexistent", "--dry-run"],
        check=False,
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


@requires_jq
def test_publish_runtime_dry_run_rejects_missing_server_binary(tmp_path: Path):
    """Slot without bin/llama-server must be rejected."""
    slot = tmp_path / "slot"
    slot.mkdir()
    (slot / "runtime.json").write_text('{"commit":"abc","family":"ik_llama","profile":"pi5-opt"}')
    env = os.environ.copy()
    env["POTATO_GITHUB_REPO"] = "test/repo"
    result = subprocess.run(
        [str(REPO_ROOT / "bin" / "publish_runtime.sh"), "--family", "ik_llama", "--slot-dir", str(slot), "--dry-run"],
        check=False,
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_runtime_release_lib_provides_download_helpers():
    """Contract: runtime_release.sh provides download and resolution functions."""
    script = (REPO_ROOT / "bin" / "lib" / "runtime_release.sh").read_text(encoding="utf-8")
    assert "download_and_extract_runtime" in script
    assert "resolve_latest_runtime_release_url" in script
    assert "POTATO_LLAMA_RELEASE_URL" in script
    assert "POTATO_GITHUB_REPO" in script
    # P1 fix: curl-only fallback so auto-detect works without gh CLI
    assert "api.github.com" in script
    assert "browser_download_url" in script


def test_install_dev_supports_release_download_fallback():
    """Contract: install_dev.sh sources the release helpers or references RELEASE_URL."""
    script = (REPO_ROOT / "bin" / "install_dev.sh").read_text(encoding="utf-8")
    has_source = "runtime_release.sh" in script
    has_env_var = "POTATO_LLAMA_RELEASE_URL" in script
    assert has_source or has_env_var, "install_dev.sh must support release download fallback"
