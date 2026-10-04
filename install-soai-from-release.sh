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
    source "${SCRIPT_DIR}/backend/core/bootstrap/launcher_posix/update_recovery.sh"
    echo "--fast installs to the platform system target and requires root privileges." >&2
    soai_launcher__exec_as_root preserve-environment "${SCRIPT_DIR}/install-soai-from-release.sh" "$@" || exit 1
fi

if [ "$SOAI_INSTALL_SCRIPT_HAS_COMMAND" = "1" ]; then
    exec "${SCRIPT_DIR}/soai.sh" "$@"
fi

exec "${SCRIPT_DIR}/soai.sh" install "$@"
