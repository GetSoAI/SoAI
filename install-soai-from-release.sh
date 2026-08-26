#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOAI_INSTALL_SCRIPT_HAS_COMMAND=0
SOAI_INSTALL_SCRIPT_FAST=0

for soai_install_script_arg in "$@"; do
    case "$soai_install_script_arg" in
        install|--install|-install|install-deps|--install-deps|-install-deps)
            SOAI_INSTALL_SCRIPT_HAS_COMMAND=1
            ;;
        --fast|-fast)
            SOAI_INSTALL_SCRIPT_FAST=1
            ;;
        *) ;;
    esac
done

if [ "$SOAI_INSTALL_SCRIPT_FAST" = "1" ] && [ "${EUID:-$(id -u)}" -ne 0 ]; then
    if ! command -v sudo >/dev/null 2>&1; then
        echo "ERROR: --fast installs to the platform system target and requires root privileges, but sudo is unavailable." >&2
        exit 1
    fi
    exec sudo -E "${SCRIPT_DIR}/install-soai-from-release.sh" "$@"
fi

if [ "$SOAI_INSTALL_SCRIPT_HAS_COMMAND" = "1" ]; then
    exec "${SCRIPT_DIR}/soai.sh" "$@"
fi

exec "${SCRIPT_DIR}/soai.sh" install "$@"
