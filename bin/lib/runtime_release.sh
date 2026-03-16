#!/usr/bin/env bash
# Shared helpers for downloading runtime binaries from GitHub Releases.
# Sourced by install_dev.sh, prepare_imager_bundle.sh, and image/lib/common.sh.

POTATO_GITHUB_REPO="${POTATO_GITHUB_REPO:-slomin/potato-os}"

resolve_latest_runtime_release_url() {
  local family="$1"
  if ! command -v gh >/dev/null 2>&1; then
    return
  fi
  local tag
  tag="$(gh release list --repo "${POTATO_GITHUB_REPO}" --limit 20 \
    --json tagName --jq "[.[] | select(.tagName | startswith(\"runtime/${family}-\"))] | .[0].tagName" 2>/dev/null || true)"
  if [ -z "${tag}" ]; then
    return
  fi
  gh release view "${tag}" --repo "${POTATO_GITHUB_REPO}" \
    --json assets --jq '.assets[0].url' 2>/dev/null || true
}

download_and_extract_runtime() {
  local url="$1"
  local target_dir="$2"
  local tmp_tarball
  tmp_tarball="$(mktemp /tmp/potato-runtime-XXXXXX.tar.gz)"

  printf 'Downloading runtime from %s\n' "${url}"
  if ! curl -L --fail --silent --show-error --output "${tmp_tarball}" "${url}"; then
    printf 'WARNING: Failed to download runtime from %s\n' "${url}" >&2
    rm -f "${tmp_tarball}"
    return 1
  fi

  rm -rf "${target_dir}"
  mkdir -p "${target_dir}"
  tar -xzf "${tmp_tarball}" -C "${target_dir}" --strip-components=1
  rm -f "${tmp_tarball}"

  if [ ! -x "${target_dir}/bin/llama-server" ]; then
    printf 'WARNING: Downloaded runtime is missing bin/llama-server\n' >&2
    rm -rf "${target_dir}"
    return 1
  fi
  printf 'Runtime downloaded and extracted to %s\n' "${target_dir}"
}

try_resolve_runtime_from_release() {
  local family="$1"
  local target_dir="$2"

  local release_url="${POTATO_LLAMA_RELEASE_URL:-}"
  if [ -z "${release_url}" ] && [ "${POTATO_LLAMA_RELEASE_AUTO:-0}" = "1" ]; then
    release_url="$(resolve_latest_runtime_release_url "${family}" || true)"
  fi

  if [ -n "${release_url}" ]; then
    if download_and_extract_runtime "${release_url}" "${target_dir}"; then
      printf '%s\n' "${target_dir}"
      return 0
    fi
  fi
  return 1
}
