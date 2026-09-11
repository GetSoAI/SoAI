#!/usr/bin/env bash
# SoAI - POSIX launcher update recovery policy [backend/core/bootstrap/launcher_posix/update_recovery.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_launcher__legacy_update_lock_active() {
    local lock_dir="${SCRIPT_DIR}/data/locks/soai.update.lock.d"
    if [ -e "${lock_dir}/process.json" ] || [ -L "${lock_dir}/process.json" ]; then
        return 1
    fi
    local pid_file="${lock_dir}/pid"
    local lock_pid
    if [ -L "$lock_dir" ] || [ ! -d "$lock_dir" ] || [ -L "$pid_file" ] || [ ! -f "$pid_file" ]; then
        return 1
    fi
    lock_pid="$(cat "$pid_file" 2>/dev/null || true)"
    case "$lock_pid" in
        ''|0|*[!0-9]*) return 1 ;;
    esac
    kill -0 "$lock_pid" >/dev/null 2>&1
}

soai_launcher__elevate_for_installed_state() {
    if [ "$(uname -s 2>/dev/null || true)" != "Linux" ] || [ "${EUID:-$(id -u)}" -eq 0 ]; then
        return 0
    fi
    local launcher_state_dir="${SCRIPT_DIR}/data/state"
    if [ ! -d "$launcher_state_dir" ] || [ -w "$launcher_state_dir" ]; then
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        echo "ERROR: SoAI requires root privileges for this installation, but sudo is unavailable." >&2
        return 1
    fi
    soai_launcher__info "Root privileges are required to manage this SoAI installation."
    exec sudo -- "${SCRIPT_DIR}/${SOAI_EXPLICIT_LAUNCHER_RELATIVE_PATH}" "$@"
}

soai_launcher__recover_update_transactions() {
    local transaction_path
    local recovery_required=0
    local recovery_backend="${SCRIPT_DIR}/backend"
    local retained_backend_count=0
    shopt -s nullglob
    for transaction_path in "${SCRIPT_DIR}"/.soai_update_transaction_* "${SCRIPT_DIR}"/.soai_update_cleanup_*; do
        recovery_required=1
        if [[ "$transaction_path" = "${SCRIPT_DIR}/.soai_update_transaction_"* ]] \
            && [ -f "${transaction_path}/rollback_required" ] \
            && [ -f "${transaction_path}/old_complete" ] \
            && [ ! -f "${transaction_path}/success_complete" ] \
            && [ ! -f "${transaction_path}/rollback_complete" ] \
            && [ -d "${transaction_path}/old/backend" ]; then
            if [ -L "$transaction_path" ] || [ -L "${transaction_path}/old" ] || [ -L "${transaction_path}/old/backend" ]; then
                echo "ERROR: Retained update recovery storage cannot be a symbolic link; evidence was preserved." >&2
                return 1
            fi
            recovery_backend="${transaction_path}/old/backend"
            retained_backend_count=$((retained_backend_count + 1))
        fi
    done
    shopt -u nullglob
    [ "$recovery_required" = "1" ] || return 0
    soai_launcher__elevate_for_installed_state "$@" || return 1
    if [ "$retained_backend_count" -gt 1 ]; then
        echo "ERROR: Multiple update originals require repair; recovery cannot select an implementation safely." >&2
        return 1
    fi
    if soai_launcher__legacy_update_lock_active; then
        echo "ERROR: SoAI software update is in progress; startup recovery is deferred." >&2
        return 1
    fi
    local runtime_path="${SOAI_VENV_PATH:-${SCRIPT_DIR}/soai_main_venv}"
    case "$runtime_path" in
        /*) ;;
        *) runtime_path="${SCRIPT_DIR}/${runtime_path}" ;;
    esac
    local python_path="${runtime_path}/bin/python"
    if [ ! -x "$python_path" ]; then
        echo "ERROR: Update recovery requires the installed managed Python runtime; transaction evidence was retained." >&2
        return 1
    fi
    (
        cd "$recovery_backend" || exit 1
        PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$recovery_backend" \
            "$python_path" -S -m app.updater.software_update.recovery_bootstrap "$SCRIPT_DIR"
    )
}
