#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/backend/core/bootstrap/filename_digests.json" ] && [ -f "${SCRIPT_DIR}/install-soai-from-release.sh" ]; then
    exec "${SCRIPT_DIR}/install-soai-from-release.sh" "$@"
fi
exec "${SCRIPT_DIR}/install_soai_from_release.sh" "$@"
