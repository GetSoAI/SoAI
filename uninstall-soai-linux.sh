#!/usr/bin/env bash
# SoAI - Linux installation removal [uninstall-soai-linux.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0
set -euo pipefail

SOAI_UNINSTALL_SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/$(basename "${BASH_SOURCE[0]}")"
SOAI_UNINSTALL_ROOT="$(dirname "$SOAI_UNINSTALL_SCRIPT_PATH")"
SOAI_UNINSTALL_UNIT_PATH="/etc/systemd/system/soai.service"
SOAI_UNINSTALL_COMMAND_PATH="/usr/local/bin/soai"
SOAI_UNINSTALL_BLOCKED_ROOTS="/ /boot /etc /home /opt /root /srv /usr /var"
SOAI_UNINSTALL_EDITION=""
SOAI_UNINSTALL_ASSUME_YES=0
SOAI_UNINSTALL_KEEP_DATA=0
SOAI_UNINSTALL_DRY_RUN=0
SOAI_UNINSTALL_REMOVE_UNIT=0
SOAI_UNINSTALL_REMOVE_COMMAND=0
SOAI_UNINSTALL_TARGETS=()

soai_uninstall__status() {
    printf ">>> %s\n" "$*" >&2
}

soai_uninstall__die() {
    printf "ERROR: %s\n" "$*" >&2
    exit 1
}

soai_uninstall__managed_root_entries() {
    printf "%s\n" \
        backend frontend plugins licenses docs \
        VERSION release-info-v1.json CHANGE-DATES.md COMMERCIAL-LICENSING-AVAILABILITY.md COMMERCIAL-LICENSE.md \
        COMMERCIAL-SUPPORT-TERMS.md LICENSE.md README.md NOTICE LICENSING.md \
        PRIVACY.md ORGANIZATION-EVALUATION-TERMS.md DOCUMENTATION.md SECURITY.md \
        RELEASE_NOTES.md requirements.txt install-soai-macos.command install-soai-windows.ps1 install-soai-linux.sh \
        soai.sh soai.command soai.exe install-soai-from-release.sh install-soai-from-release.command \
        install-soai-from-release.bat uninstall-soai-linux.sh
    if [ "$SOAI_UNINSTALL_EDITION" = "soai-os" ]; then
        printf "%s\n" soai_os
    fi
}

soai_uninstall__runtime_root_entries() {
    printf "%s\n" soai_main_venv __pycache__ restart_purge.log \
        restart_purge.manifest.json restart_purge.sentinel \
        .soai_install_manifest.json .soai_install_in_progress
    if [ "$SOAI_UNINSTALL_KEEP_DATA" = "0" ]; then
        printf "%s\n" data
    fi
}

soai_uninstall__require_supported_platform() {
    if [ "$(uname -s 2>/dev/null || true)" != "Linux" ]; then
        soai_uninstall__die "This uninstaller supports Linux only."
    fi
}

soai_uninstall__require_removable_root() {
    if [ ! -d "$SOAI_UNINSTALL_ROOT" ]; then
        soai_uninstall__die "Installation directory does not exist: ${SOAI_UNINSTALL_ROOT}"
    fi
    case " $SOAI_UNINSTALL_BLOCKED_ROOTS " in
        *" $SOAI_UNINSTALL_ROOT "*)
            soai_uninstall__die "Refusing to uninstall from a system directory: ${SOAI_UNINSTALL_ROOT}"
            ;;
    esac
    if [ -n "${HOME:-}" ] && [ "$SOAI_UNINSTALL_ROOT" = "$HOME" ]; then
        soai_uninstall__die "Refusing to uninstall from the home directory: ${SOAI_UNINSTALL_ROOT}"
    fi
    if [ -e "${SOAI_UNINSTALL_ROOT}/.git" ]; then
        soai_uninstall__die "Refusing to uninstall a Git working tree: ${SOAI_UNINSTALL_ROOT}"
    fi
}

soai_uninstall__require_soai_root() {
    local manifest="${SOAI_UNINSTALL_ROOT}/.soai_install_manifest.json"
    if [ -f "$manifest" ] && [ ! -L "$manifest" ]; then
        if ! grep -q '"product"[[:space:]]*:[[:space:]]*"SoAI"' "$manifest"; then
            soai_uninstall__die "Install manifest does not describe a SoAI installation: ${manifest}"
        fi
        return 0
    fi
    if [ -f "${SOAI_UNINSTALL_ROOT}/.soai_install_in_progress" ]; then
        return 0
    fi
    if [ -f "${SOAI_UNINSTALL_ROOT}/soai.sh" ] && [ -f "${SOAI_UNINSTALL_ROOT}/backend/main.py" ]; then
        return 0
    fi
    soai_uninstall__die "No SoAI installation was found in ${SOAI_UNINSTALL_ROOT}."
}

soai_uninstall__resolve_edition() {
    local manifest="${SOAI_UNINSTALL_ROOT}/.soai_install_manifest.json"
    local edition=""
    if [ -f "$manifest" ]; then
        edition="$(sed -n 's/.*"edition"[[:space:]]*:[[:space:]]*"\([a-z-]*\)".*/\1/p' "$manifest" | head -n 1)"
    fi
    if [ -z "$edition" ] && [ -f "${SOAI_UNINSTALL_ROOT}/soai_os/soai-os.sh" ]; then
        edition="soai-os"
    fi
    if [ "$edition" != "soai-os" ]; then
        edition="soai-core"
    fi
    SOAI_UNINSTALL_EDITION="$edition"
}

soai_uninstall__root_owns_live_process() {
    local proc_entry=""
    local exe_target=""
    for proc_entry in /proc/[0-9]*; do
        exe_target="$(readlink "${proc_entry}/exe" 2>/dev/null || true)"
        if [ -z "$exe_target" ]; then
            continue
        fi
        case "$exe_target" in
            "${SOAI_UNINSTALL_ROOT}"/*) return 0 ;;
        esac
    done
    return 1
}

soai_uninstall__instance_is_running() {
    if soai_uninstall__root_owns_live_process; then
        return 0
    fi
    local lock_pid="${SOAI_UNINSTALL_ROOT}/data/state/locks/soai.runtime.lock.d/pid"
    local record="${SOAI_UNINSTALL_ROOT}/data/temp/soai.pid"
    local owner_pid=""
    if [ -d "${lock_pid%/pid}" ]; then
        if [ ! -f "$lock_pid" ]; then
            return 0
        fi
        owner_pid="$(cat "$lock_pid" 2>/dev/null || true)"
        if [ -n "$owner_pid" ] && kill -0 "$owner_pid" >/dev/null 2>&1; then
            return 0
        fi
    fi
    if [ ! -f "$record" ]; then
        return 1
    fi
    owner_pid="$(sed -n 's/.*"pid"[[:space:]]*:[[:space:]]*\([0-9]\{1,\}\).*/\1/p' "$record" | head -n 1)"
    [ -n "$owner_pid" ] && kill -0 "$owner_pid" >/dev/null 2>&1
}

soai_uninstall__unit_belongs_to_root() {
    if [ ! -f "$SOAI_UNINSTALL_UNIT_PATH" ]; then
        return 1
    fi
    grep -Fxq "WorkingDirectory=${SOAI_UNINSTALL_ROOT}" "$SOAI_UNINSTALL_UNIT_PATH" || \
        grep -Fq "ExecStart=${SOAI_UNINSTALL_ROOT}/" "$SOAI_UNINSTALL_UNIT_PATH"
}

soai_uninstall__command_belongs_to_root() {
    [ -L "$SOAI_UNINSTALL_COMMAND_PATH" ] \
        && [ "$(readlink "$SOAI_UNINSTALL_COMMAND_PATH")" = "${SOAI_UNINSTALL_ROOT}/soai.sh" ]
}

soai_uninstall__collect_targets() {
    local entry=""
    local path=""
    while IFS= read -r entry; do
        path="${SOAI_UNINSTALL_ROOT}/${entry}"
        if [ -e "$path" ] || [ -L "$path" ]; then
            SOAI_UNINSTALL_TARGETS+=("$path")
        fi
    done < <(soai_uninstall__managed_root_entries; soai_uninstall__runtime_root_entries)
    for entry in ".soai_install_staging." ".soai_install_previous." ".soai_update_transaction_"; do
        for path in "${SOAI_UNINSTALL_ROOT}/${entry}"*; do
            if [ -e "$path" ] || [ -L "$path" ]; then
                SOAI_UNINSTALL_TARGETS+=("$path")
            fi
        done
    done
}

soai_uninstall__print_help() {
    cat <<'USAGE'
usage: uninstall-soai-linux.sh [OPTIONS]

Remove the SoAI installation that contains this script from the local Linux system.
Application files, the managed runtime, and the systemd service of this installation
are removed. Files SoAI did not install, data directories configured outside the
installation directory, and shared system packages are kept.

options:
  -h, --help       Print this help message and exit.
  -y, --yes        Remove without asking for interactive confirmation.
      --keep-data  Keep the data directory (models, database, chats, logs, config).
      --dry-run    Print what would be removed and exit without changing anything.
USAGE
}

soai_uninstall__parse_arguments() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            -h|--help|help) soai_uninstall__print_help; exit 0 ;;
            -y|--yes) SOAI_UNINSTALL_ASSUME_YES=1 ;;
            --keep-data) SOAI_UNINSTALL_KEEP_DATA=1 ;;
            --dry-run) SOAI_UNINSTALL_DRY_RUN=1 ;;
            *) soai_uninstall__die "Unknown option: $1. Run uninstall-soai-linux.sh --help for usage." ;;
        esac
        shift
    done
}

soai_uninstall__print_plan() {
    local path=""
    soai_uninstall__status "SoAI installation: ${SOAI_UNINSTALL_ROOT} (${SOAI_UNINSTALL_EDITION})"
    if [ "${#SOAI_UNINSTALL_TARGETS[@]}" -eq 0 ]; then
        soai_uninstall__status "Nothing to remove."
    else
        soai_uninstall__status "The following paths will be removed:"
        for path in "${SOAI_UNINSTALL_TARGETS[@]}"; do
            printf "  - %s\n" "$path" >&2
        done
    fi
    if [ "$SOAI_UNINSTALL_REMOVE_UNIT" = "1" ]; then
        soai_uninstall__status "The systemd service of this installation is removed: ${SOAI_UNINSTALL_UNIT_PATH}"
    elif [ -f "$SOAI_UNINSTALL_UNIT_PATH" ]; then
        soai_uninstall__status "Keeping ${SOAI_UNINSTALL_UNIT_PATH} because it serves a different installation."
    fi
    if [ "$SOAI_UNINSTALL_REMOVE_COMMAND" = "1" ]; then
        soai_uninstall__status "The command of this installation is removed: ${SOAI_UNINSTALL_COMMAND_PATH}"
    elif [ -e "$SOAI_UNINSTALL_COMMAND_PATH" ] || [ -L "$SOAI_UNINSTALL_COMMAND_PATH" ]; then
        soai_uninstall__status "Keeping ${SOAI_UNINSTALL_COMMAND_PATH} because it belongs to a different installation."
    fi
    soai_uninstall__status "Data directories configured outside ${SOAI_UNINSTALL_ROOT} and shared system packages are kept."
}

soai_uninstall__confirm() {
    local response=""
    if [ "$SOAI_UNINSTALL_ASSUME_YES" = "1" ]; then
        return 0
    fi
    if ! (exec 3<>/dev/tty) 2>/dev/null; then
        soai_uninstall__die "No interactive terminal is available. Re-run with --yes to remove SoAI without confirmation."
    fi
    if ! read -r -p "Remove this SoAI installation? [y/N] " response < /dev/tty; then
        response=""
    fi
    case "$response" in
        y|Y|yes|YES|Yes) return 0 ;;
        *) ;;
    esac
    soai_uninstall__status "Uninstall cancelled."
    exit 1
}

soai_uninstall__elevate_if_required() {
    local needs_root=0
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        return 0
    fi
    if [ ! -w "$SOAI_UNINSTALL_ROOT" ] || [ ! -w "$(dirname "$SOAI_UNINSTALL_ROOT")" ]; then
        needs_root=1
    fi
    if [ "$SOAI_UNINSTALL_REMOVE_UNIT" = "1" ] && [ ! -w "$(dirname "$SOAI_UNINSTALL_UNIT_PATH")" ]; then
        needs_root=1
    fi
    if [ "$SOAI_UNINSTALL_REMOVE_COMMAND" = "1" ] && [ ! -w "$(dirname "$SOAI_UNINSTALL_COMMAND_PATH")" ]; then
        needs_root=1
    fi
    if [ "$needs_root" = "0" ]; then
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        soai_uninstall__die "Root privileges are required to remove ${SOAI_UNINSTALL_ROOT}, but sudo is unavailable."
    fi
    soai_uninstall__status "Root privileges are required to remove ${SOAI_UNINSTALL_ROOT}."
    exec sudo -E bash "$SOAI_UNINSTALL_SCRIPT_PATH" "$@" --yes
}

soai_uninstall__remove_service() {
    if [ "$SOAI_UNINSTALL_REMOVE_UNIT" != "1" ]; then
        return 0
    fi
    soai_uninstall__status "Removing the SoAI systemd service..."
    if command -v systemctl >/dev/null 2>&1; then
        systemctl disable --now soai.service >/dev/null 2>&1 || true
    fi
    rm -f -- "$SOAI_UNINSTALL_UNIT_PATH" || soai_uninstall__die "Failed to remove ${SOAI_UNINSTALL_UNIT_PATH}."
    if command -v systemctl >/dev/null 2>&1; then
        systemctl daemon-reload >/dev/null 2>&1 || true
        systemctl reset-failed soai.service >/dev/null 2>&1 || true
    fi
}

soai_uninstall__remove_command() {
    if [ "$SOAI_UNINSTALL_REMOVE_COMMAND" != "1" ]; then
        return 0
    fi
    if ! soai_uninstall__command_belongs_to_root; then
        soai_uninstall__die "Refusing to remove a SoAI command that no longer belongs to this installation: ${SOAI_UNINSTALL_COMMAND_PATH}"
    fi
    rm -f -- "$SOAI_UNINSTALL_COMMAND_PATH" || soai_uninstall__die "Failed to remove ${SOAI_UNINSTALL_COMMAND_PATH}."
}

soai_uninstall__remove_targets() {
    local path=""
    for path in "${SOAI_UNINSTALL_TARGETS[@]:-}"; do
        if [ -z "$path" ]; then
            continue
        fi
        case "$path" in
            "${SOAI_UNINSTALL_ROOT}"/*) ;;
            *) soai_uninstall__die "Refusing to remove a path outside the installation: ${path}" ;;
        esac
        rm -rf -- "$path" || soai_uninstall__die "Failed to remove: ${path}"
    done
}

soai_uninstall__finish_root() {
    if [ -z "$(find "$SOAI_UNINSTALL_ROOT" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
        if rmdir "$SOAI_UNINSTALL_ROOT" 2>/dev/null; then
            soai_uninstall__status "Removed the SoAI installation directory: ${SOAI_UNINSTALL_ROOT}"
            return 0
        fi
        soai_uninstall__status "SoAI files were removed but the empty directory remains: ${SOAI_UNINSTALL_ROOT}"
        return 0
    fi
    soai_uninstall__status "Kept ${SOAI_UNINSTALL_ROOT} because it still contains:"
    find "$SOAI_UNINSTALL_ROOT" -mindepth 1 -maxdepth 1 -printf "  - %f\n" >&2
}

soai_uninstall__main() {
    soai_uninstall__parse_arguments "$@"
    soai_uninstall__require_supported_platform
    soai_uninstall__require_removable_root
    soai_uninstall__require_soai_root
    soai_uninstall__resolve_edition
    if soai_uninstall__instance_is_running; then
        soai_uninstall__die "SoAI is running from ${SOAI_UNINSTALL_ROOT}. Stop it first, then run uninstall-soai-linux.sh again."
    fi
    if soai_uninstall__unit_belongs_to_root; then
        SOAI_UNINSTALL_REMOVE_UNIT=1
    fi
    if soai_uninstall__command_belongs_to_root; then
        SOAI_UNINSTALL_REMOVE_COMMAND=1
    fi
    soai_uninstall__collect_targets
    soai_uninstall__print_plan
    if [ "$SOAI_UNINSTALL_DRY_RUN" = "1" ]; then
        soai_uninstall__status "Dry run completed. Nothing was changed."
        return 0
    fi
    soai_uninstall__confirm
    soai_uninstall__elevate_if_required "$@"
    soai_uninstall__remove_service
    soai_uninstall__remove_command
    soai_uninstall__remove_targets
    soai_uninstall__finish_root
    soai_uninstall__status "SoAI uninstall completed."
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    soai_uninstall__main "$@"
fi
