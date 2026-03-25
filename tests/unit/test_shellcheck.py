"""shellcheck lint for all shell scripts in the repository.

Replaces the former ``bash -n`` syntax tests with full shellcheck analysis.
Skipped locally when shellcheck is not installed; always runs in CI.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from tests.unit.conftest import REPO_ROOT

SHELL_SCRIPTS = [
    "bin/run.sh",
    "bin/start_llama.sh",
    "bin/install_dev.sh",
    "bin/uninstall_dev.sh",
    "bin/firstboot.sh",
    "bin/ensure_model.sh",
    "bin/prepare_imager_bundle.sh",
    "bin/publish_ota_release.sh",
    "bin/publish_runtime.sh",
    "bin/publish_image_release.sh",
    "bin/build_local_image.sh",
    "bin/build_llama_bundle_pi5.sh",
    "bin/build_llama_runtime.sh",
    "bin/build_and_publish_remote.sh",
    "bin/reset_runtime.sh",
    "bin/clean_image_build_artifacts.sh",
    "bin/install_openclaw.sh",
    "bin/uninstall_openclaw.sh",
    "bin/lib/branding.sh",
    "bin/lib/build_helpers.sh",
    "bin/lib/runtime_release.sh",
    "image/build-lite.sh",
    "image/build-full.sh",
    "image/build-all.sh",
    "image/lib/common.sh",
    "image/stage-potato/prerun.sh",
    "image/stage-potato/00-potato/00-run.sh",
    "tests/e2e/smoke_pi.sh",
    "tests/e2e/stream_chat_pi.sh",
    "tests/e2e/vision_multi_image_pi.sh",
    "tests/e2e/uninstall_pi.sh",
    "tests/e2e/ota_update_pi.sh",
    "tests/e2e/seed_mode_pi.sh",
]


@pytest.mark.parametrize("script", SHELL_SCRIPTS, ids=lambda s: s.replace("/", "_"))
def test_shellcheck(script: str) -> None:
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck not installed")
    path = REPO_ROOT / script
    assert path.exists(), f"{script} not found"
    result = subprocess.run(
        ["shellcheck", "-x", "-S", "warning", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"shellcheck {script}:\n{result.stdout}\n{result.stderr}"
