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

SOAI_LAUNCHER_ROOT_PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SOAI_LAUNCHER_ROOT_SU_ATTEMPTS=3
SOAI_LAUNCHER_SUDO_VALIDATION=""

soai_launcher__root_terminal_available() {
    (exec 3</dev/tty) 2>/dev/null
}

soai_launcher__sudo_permits_command() {
    local sudo_probe_output=""
    if sudo_probe_output="$(LC_ALL=C sudo -n -l -- "$@" 2>&1)"; then
        return 0
    fi
    case "$sudo_probe_output" in
        *"a password is required"*|*"interactive authentication is required"*) return 0 ;;
    esac
    return 1
}

soai_launcher__elevation_status() {
    if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then
        soai_install_ui__message information "$1"
        return
    fi
    local color=""
    local reset=""
    if [ -t 2 ] && [ "${TERM:-dumb}" != dumb ] && [ -z "${NO_COLOR+x}" ]; then
        color=$'\033[38;5;215m'
        reset=$'\033[0m'
    fi
    printf '%s>%s %s\n' "$color" "$reset" "$1" >&2
}

soai_launcher__sudo_preserved_environment_names() {
    local environment_policy="$1"
    local names=""
    local name=""
    if [ "$environment_policy" != "preserve-environment" ]; then
        return 0
    fi
    while IFS= read -r name; do
        if [ "$name" != "PATH" ]; then
            names="${names:+${names},}${name}"
        fi
    done < <(compgen -e)
    printf '%s' "$names"
}

soai_launcher__select_root_elevation() {
    SOAI_LAUNCHER_ROOT_ELEVATION=""
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        SOAI_LAUNCHER_ROOT_ELEVATION="root"
        return 0
    fi
    if [ "$SOAI_LAUNCHER_SUDO_VALIDATION" != "failed" ] && command -v sudo >/dev/null 2>&1; then
        if ! sudo -v; then
            SOAI_LAUNCHER_SUDO_VALIDATION="failed"
        fi
    fi
    if [ "$SOAI_LAUNCHER_SUDO_VALIDATION" != "failed" ] && command -v sudo >/dev/null 2>&1; then
        if soai_launcher__sudo_permits_command "$@"; then
            SOAI_LAUNCHER_ROOT_ELEVATION="sudo"
            return 0
        fi
        if command -v su >/dev/null 2>&1 \
            && soai_launcher__sudo_permits_command su -s /bin/bash root -c true; then
            SOAI_LAUNCHER_ROOT_ELEVATION="sudo-su"
            return 0
        fi
    fi
    if command -v su >/dev/null 2>&1 && soai_launcher__root_terminal_available; then
        SOAI_LAUNCHER_ROOT_ELEVATION="su"
        return 0
    fi
    return 1
}

soai_launcher__root_shell_command() {
    printf '%q ' env "PATH=${SOAI_LAUNCHER_ROOT_PATH}" "$@"
}

soai_launcher__run_with_su() {
    local started_directory=""
    if ! started_directory="$(mktemp -d)"; then
        echo "ERROR: Could not create a temporary directory for root privilege elevation." >&2
        return 1
    fi
    local root_command=""
    root_command="$(printf '%q ' touch -- "${started_directory}/started")&& exec $(soai_launcher__root_shell_command "$@")"
    local attempt=1
    local status=0
    while [ "$attempt" -le "$SOAI_LAUNCHER_ROOT_SU_ATTEMPTS" ]; do
        soai_launcher__elevation_status "Enter the root password for su (attempt ${attempt}/${SOAI_LAUNCHER_ROOT_SU_ATTEMPTS})."
        status=0
        su -s /bin/bash root -c "$root_command" </dev/tty || status=$?
        if [ -e "${started_directory}/started" ] || [ "$status" -gt 128 ]; then
            rm -rf -- "$started_directory"
            return "$status"
        fi
        attempt=$((attempt + 1))
    done
    rm -rf -- "$started_directory"
    echo "ERROR: Could not obtain root privileges through su." >&2
    return 1
}

soai_launcher__report_root_elevation_unavailable() {
    echo "ERROR: SoAI requires root privileges, but neither sudo nor su can provide them for this user. Run the command as root." >&2
}

soai_launcher__run_as_root() {
    local environment_policy="$1"
    shift
    if ! soai_launcher__select_root_elevation "$@"; then
        soai_launcher__report_root_elevation_unavailable
        return 1
    fi
    case "$SOAI_LAUNCHER_ROOT_ELEVATION" in
        root) "$@" ;;
        sudo)
            local preserved_names=""
            preserved_names="$(soai_launcher__sudo_preserved_environment_names "$environment_policy")"
            if [ -n "$preserved_names" ]; then
                sudo "--preserve-env=${preserved_names}" -- "$@"
            else
                sudo -- "$@"
            fi
            ;;
        sudo-su)
            soai_launcher__elevation_status "Obtaining root privileges through sudo su."
            sudo su -s /bin/bash root -c "$(soai_launcher__root_shell_command "$@")"
            ;;
        su) soai_launcher__run_with_su "$@" ;;
    esac
}

soai_launcher__exec_as_root() {
    local environment_policy="$1"
    shift
    if ! soai_launcher__select_root_elevation "$@"; then
        soai_launcher__report_root_elevation_unavailable
        return 1
    fi
    case "$SOAI_LAUNCHER_ROOT_ELEVATION" in
        root) exec "$@" ;;
        sudo)
            local preserved_names=""
            preserved_names="$(soai_launcher__sudo_preserved_environment_names "$environment_policy")"
            if [ -n "$preserved_names" ]; then
                exec sudo "--preserve-env=${preserved_names}" -- "$@"
            fi
            exec sudo -- "$@"
            ;;
        sudo-su)
            soai_launcher__elevation_status "Obtaining root privileges through sudo su."
            exec sudo su -s /bin/bash root -c "$(soai_launcher__root_shell_command "$@")"
            ;;
        su)
            local status=0
            trap ':' INT
            soai_launcher__run_with_su "$@" || status=$?
            trap - INT
            exit "$status"
            ;;
    esac
}

soai_launcher__elevate_for_installed_state() {
    if [ "$(uname -s 2>/dev/null || true)" != "Linux" ] || [ "${EUID:-$(id -u)}" -eq 0 ]; then
        return 0
    fi
    local launcher_state_dir="${SCRIPT_DIR}/data/state"
    if [ ! -d "$launcher_state_dir" ] || [ -w "$launcher_state_dir" ]; then
        return 0
    fi
    soai_launcher__elevation_status "Root privileges are required to manage the SoAI installation in ${SCRIPT_DIR}."
    soai_launcher__exec_as_root default-environment "${SCRIPT_DIR}/${SOAI_EXPLICIT_LAUNCHER_RELATIVE_PATH}" "$@"
}

soai_launcher__recover_update_transactions() {
    case "${1:-}" in
        install-deps|--install-deps|-install-deps)
            local install_lock_dir="${SCRIPT_DIR}/data/state/locks/soai.install.lock.d"
            if [ "${SOAI_INSTALL_LOCK_HELD_PATH:-}" = "$install_lock_dir" ]; then
                source "${SCRIPT_DIR}/backend/core/bootstrap/launcher_posix/runtime_locks.sh" || return 1
                if soai_managed_runtime__inherited_install_lock_is_parent_owned "$install_lock_dir"; then
                    return 0
                fi
                echo "ERROR: Inherited installer ownership cannot be verified; update evidence was retained." >&2
                return 1
            fi
            ;;
    esac
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
