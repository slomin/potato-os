#!/usr/bin/env bash
set -euo pipefail

# Build llama runtimes on a remote Pi and publish to GitHub Releases.
#
# Usage (from Mac):
#   ./bin/build_and_publish_remote.sh
#   ./bin/build_and_publish_remote.sh --family ik_llama
#   ./bin/build_and_publish_remote.sh --family both --publish
#   ./bin/build_and_publish_remote.sh --build-only
#
# Requires: sshpass, rsync, ssh, gh (for publish)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_HOST="${POTATO_PI_HOST:-potato.local}"
PI_USER="${POTATO_PI_USER:-pi}"
PI_PASSWORD="${POTATO_PI_PASSWORD:-raspberry}"
FAMILY="${POTATO_LLAMA_RUNTIME_FAMILY:-both}"
DO_PUBLISH="${POTATO_PUBLISH:-0}"
BUILD_ONLY=0
REMOTE_REPO_DIR="/tmp/potato-os"
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"

usage() {
  cat <<'EOF'
Usage:
  ./bin/build_and_publish_remote.sh [--family ik_llama|llama_cpp|both] [--publish] [--build-only]

Syncs the repo to a Pi, builds runtime(s) from latest source, syncs
the built slots back to your Mac, and optionally publishes to GitHub Releases.

Options:
  --family <name>   Runtime family to build (default: both)
  --publish         Also publish to GitHub Releases after building
  --build-only      Build on Pi but don't sync back or publish
  --host <host>     Pi hostname (default: potato.local)
  -h, --help        Show this help

Environment:
  POTATO_PI_HOST       Pi hostname (default: potato.local)
  POTATO_PI_USER       SSH user (default: pi)
  POTATO_PI_PASSWORD   SSH password (default: raspberry)
EOF
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --family) FAMILY="$2"; shift 2 ;;
    --publish) DO_PUBLISH=1; shift ;;
    --build-only) BUILD_ONLY=1; shift ;;
    --host) PI_HOST="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

command -v sshpass >/dev/null 2>&1 || die "sshpass is required. Install with: brew install sshpass (or hudochenkov/sshpass)"
export SSHPASS="${PI_PASSWORD}"

_ssh() {
  sshpass -e ssh ${SSH_OPTS} "${PI_USER}@${PI_HOST}" "$@"
}

_rsync() {
  sshpass -e rsync -az -e "ssh ${SSH_OPTS}" "$@"
}

printf '=== Potato Runtime Remote Build ===\n'
printf 'Host:   %s\n' "${PI_HOST}"
printf 'Family: %s\n' "${FAMILY}"
printf '\n'

# ── Step 1: Sync repo to Pi ───────────────────────────────────────────
printf '[1/4] Syncing repo to %s:%s\n' "${PI_HOST}" "${REMOTE_REPO_DIR}"
_rsync --delete \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '.venv' \
  --exclude 'models/' \
  --exclude 'output/' \
  --exclude 'references/old_reference_design/llama_cpp_binary/llama_server_bundle_*' \
  "${REPO_ROOT}/" "${PI_USER}@${PI_HOST}:${REMOTE_REPO_DIR}/"

# ── Step 2: Build on Pi ───────────────────────────────────────────────
printf '[2/4] Building runtime(s) on Pi (this takes ~15 min per family)\n'
_ssh "cd ${REMOTE_REPO_DIR} && bash bin/build_llama_runtime.sh --family ${FAMILY} --fetch --clean"

if [ "${BUILD_ONLY}" = "1" ]; then
  printf '\nBuild complete (--build-only). Slots are on Pi at %s/references/old_reference_design/llama_cpp_binary/runtimes/\n' "${REMOTE_REPO_DIR}"
  exit 0
fi

# ── Step 3: Sync built slots back to Mac ──────────────────────────────
SLOTS_DIR="${REPO_ROOT}/references/old_reference_design/llama_cpp_binary/runtimes"
mkdir -p "${SLOTS_DIR}"

printf '[3/4] Syncing built runtime slots back to Mac\n'
if [ "${FAMILY}" = "both" ]; then
  for fam in ik_llama llama_cpp; do
    printf '  Syncing %s...\n' "${fam}"
    _rsync --delete \
      "${PI_USER}@${PI_HOST}:${REMOTE_REPO_DIR}/references/old_reference_design/llama_cpp_binary/runtimes/${fam}/" \
      "${SLOTS_DIR}/${fam}/"
  done
else
  printf '  Syncing %s...\n' "${FAMILY}"
  _rsync --delete \
    "${PI_USER}@${PI_HOST}:${REMOTE_REPO_DIR}/references/old_reference_design/llama_cpp_binary/runtimes/${FAMILY}/" \
    "${SLOTS_DIR}/${FAMILY}/"
fi

# ── Step 4: Publish (optional) ────────────────────────────────────────
if [ "${DO_PUBLISH}" = "1" ]; then
  printf '[4/4] Publishing to GitHub Releases\n'
  if [ "${FAMILY}" = "both" ]; then
    "${REPO_ROOT}/bin/publish_runtime.sh" --family ik_llama
    "${REPO_ROOT}/bin/publish_runtime.sh" --family llama_cpp
  else
    "${REPO_ROOT}/bin/publish_runtime.sh" --family "${FAMILY}"
  fi
else
  printf '[4/4] Skipping publish (use --publish to upload to GitHub Releases)\n'
fi

printf '\n=== Done ===\n'
if [ "${FAMILY}" = "both" ]; then
  for fam in ik_llama llama_cpp; do
    if [ -f "${SLOTS_DIR}/${fam}/runtime.json" ]; then
      printf '%s: commit %s\n' "${fam}" "$(jq -r '.commit // "unknown"' "${SLOTS_DIR}/${fam}/runtime.json")"
    fi
  done
else
  if [ -f "${SLOTS_DIR}/${FAMILY}/runtime.json" ]; then
    printf '%s: commit %s\n' "${FAMILY}" "$(jq -r '.commit // "unknown"' "${SLOTS_DIR}/${FAMILY}/runtime.json")"
  fi
fi
