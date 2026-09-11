#!/usr/bin/env bash
# SoAI - POSIX launcher main command dispatcher [backend/core/bootstrap/launcher_posix/driver.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

set -euo pipefail

SOAI_DEBUG="${SOAI_DEBUG:-0}"
if [ "${1:-}" = "debug" ] || [ "${1:-}" = "--debug" ] || [ "${1:-}" = "-debug" ]; then
    SOAI_DEBUG="1"
    shift
fi

if [ "$SOAI_DEBUG" = "1" ]; then
    export PS4='+(${BASH_SOURCE}:${LINENO}): '
    set -x
fi

if [ -z "${SOAI_EXPLICIT_ROOT:-}" ] \
    || [ -z "${SOAI_EXPLICIT_ENTRYPOINT:-}" ] \
    || [ -z "${SOAI_EXPLICIT_PYTHONPATH:-}" ] \
    || [ -z "${SOAI_EXPLICIT_EDITION:-}" ] \
    || [ -z "${SOAI_EXPLICIT_PRODUCT_VERSION:-}" ] \
    || [ -z "${SOAI_EXPLICIT_CORE_VERSION:-}" ] \
    || [ -z "${SOAI_EXPLICIT_ENTRYPOINT_RELATIVE_PATH:-}" ] \
    || [ -z "${SOAI_EXPLICIT_LAUNCHER_RELATIVE_PATH:-}" ]; then
    echo "ERROR: Launcher driver requires an explicit product root and entrypoint." >&2
    exit 1
fi
SCRIPT_DIR="$SOAI_EXPLICIT_ROOT"
MAIN_PY_PATH="$SOAI_EXPLICIT_ENTRYPOINT"
PYTHONPATH="${SOAI_EXPLICIT_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONPATH
SOAI_LAUNCHER_MODULE_DIR="${SCRIPT_DIR}/backend/core/bootstrap/launcher_posix"
source "${SOAI_LAUNCHER_MODULE_DIR}/logging.sh"
source "${SOAI_LAUNCHER_MODULE_DIR}/runtime_locks.sh"

SOAI_LAUNCHER_FAST_MANAGEMENT=0
soai_launcher_expected_install_lock_dir="${SCRIPT_DIR}/data/state/locks/soai.install.lock.d"
soai_launcher_inherited_install_lock_is_parent_owned=0
if [ "${SOAI_INSTALL_LOCK_HELD_PATH:-}" = "$soai_launcher_expected_install_lock_dir" ] \
    && soai_managed_runtime__lock_dir_is_process_owned "$soai_launcher_expected_install_lock_dir" "$PPID"; then
    soai_launcher_inherited_install_lock_is_parent_owned=1
fi

soai_launcher_should_wait_install_marker=1
soai_launcher_should_wait_install_lock=1
for soai_launcher_arg in "$@"; do
    case "$soai_launcher_arg" in
        install|--install|-install)
            soai_launcher_should_wait_install_marker=0
            ;;
        install-deps|--install-deps|-install-deps)
            if [ "$soai_launcher_inherited_install_lock_is_parent_owned" = "1" ]; then
                soai_launcher_should_wait_install_marker=0
                soai_launcher_should_wait_install_lock=0
            fi
            ;;
        *) ;;
    esac
done
if [ "$soai_launcher_should_wait_install_marker" = "1" ] || [ "$soai_launcher_should_wait_install_lock" = "1" ]; then
    soai_managed_runtime__wait_for_install_barriers \
        "${SCRIPT_DIR}/.soai_install_in_progress" \
        "$soai_launcher_expected_install_lock_dir" \
        "$soai_launcher_should_wait_install_marker" \
        "$soai_launcher_should_wait_install_lock" \
        "$SCRIPT_DIR" || exit 1
fi

for soai_launcher_module in \
    update_recovery.sh \
    runtime_environment.sh \
    runtime_environment_sqlite.sh \
    runtime_environment_tesseract.sh \
    runtime_environment_conda.sh \
    platform_preflight.sh \
    install_status.sh \
    install_target.sh \
    cli_information.sh \
    command_arguments.sh \
    opencl_provisioning.sh \
    install_payload.sh \
    install_service.sh \
    install_copy.sh \
    commands.sh
do
    source "${SOAI_LAUNCHER_MODULE_DIR}/${soai_launcher_module}"
done

soai_launcher__configure_paths() {
    SOAI_MANAGED_PYTHON="${SOAI_MANAGED_PYTHON:-3.13}"
    SOAI_MICROMAMBA_VERSION="${SOAI_MICROMAMBA_VERSION:-2.5.0}"
    SOAI_LAUNCHER_STATE_DIR="${SCRIPT_DIR}/data/state"
    SOAI_STATE_DIR="${SOAI_STATE_DIR:-$SOAI_LAUNCHER_STATE_DIR}"
    SOAI_LOCKS_PATH="${SOAI_LAUNCHER_STATE_DIR}/locks"
    PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-${SOAI_STATE_DIR}/playwright-browsers}"
    SOAI_VENV_PATH="${SOAI_VENV_PATH:-${SCRIPT_DIR}/soai_main_venv}"
    SOAI_TMP_DIR="${SOAI_TMP_DIR:-${SOAI_STATE_DIR}/tmp}"
    SOAI_PIP_CACHE_DIR="${SOAI_PIP_CACHE_DIR:-${SOAI_STATE_DIR}/pip-cache}"
    mkdir -p "$SOAI_STATE_DIR" "$SOAI_LOCKS_PATH" "$PLAYWRIGHT_BROWSERS_PATH" "$SOAI_TMP_DIR" "$SOAI_PIP_CACHE_DIR"
    export TMPDIR="$SOAI_TMP_DIR"
    export PIP_CACHE_DIR="$SOAI_PIP_CACHE_DIR"
    CONFIG_PATH="${SOAI_CONFIG_PATH:-${SCRIPT_DIR}/data/config/config.yaml}"
    OFFLINE_MODE_ENABLED="$(soai_managed_runtime__read_stay_offline "$CONFIG_PATH")"
}

soai_launcher__prepare_runtime() {
    soai_launcher__ensure_linux_host_dependencies || return 1
    soai_managed_runtime_ensure_env \
        "$SOAI_VENV_PATH" \
        "$SOAI_MANAGED_PYTHON" \
        "$SOAI_STATE_DIR" \
        "$SOAI_LOCKS_PATH" \
        "$SOAI_MICROMAMBA_VERSION" \
        "$OFFLINE_MODE_ENABLED" || return 1
}

soai_launcher__run_start() {
    soai_install__validate_existing_manifest_edition "$SOAI_EXPLICIT_ROOT" || return 1
    soai_managed_runtime__wait_for_lock_dir_clear "${SOAI_LOCKS_PATH}/soai.install.lock.d"
    local runtime_lock_dir="${SOAI_LOCKS_PATH}/soai.runtime.lock.d"
    soai_managed_runtime__acquire_lock_dir "$runtime_lock_dir" || return 1
    export SOAI_LAUNCHER_RUNTIME_LOCK_DIR="$runtime_lock_dir"
    if [ "$SOAI_LAUNCHER_FAST_MANAGEMENT" = "0" ]; then
        soai_launcher__info "Performing platform checks for the SoAI application..."
    fi
    if ! soai_launcher__run_startup_preflight "${SOAI_VENV_PATH}/bin/python"; then
        soai_managed_runtime__release_lock_dir "$runtime_lock_dir"
        return 1
    fi
    if ! soai_launcher__prepare_runtime; then
        soai_managed_runtime__release_lock_dir "$runtime_lock_dir"
        return 1
    fi
    exec "${SOAI_VENV_PATH}/bin/python" "$MAIN_PY_PATH" "${SOAI_PASSTHROUGH_ARGS[@]}"
    soai_managed_runtime__release_lock_dir "$runtime_lock_dir"
    return 1
}

soai_launcher__run_management() {
    soai_install__validate_existing_manifest_edition "$SOAI_EXPLICIT_ROOT" || return 1
    soai_managed_runtime__wait_for_lock_dir_clear "${SOAI_LOCKS_PATH}/soai.install.lock.d"
    local python_bin="${SOAI_VENV_PATH}/bin/python"
    if [ "$SOAI_LAUNCHER_FAST_MANAGEMENT" != "1" ]; then
        soai_launcher__prepare_runtime || return 1
    fi
    if [ ! -x "$python_bin" ]; then
        soai_managed_runtime__die "Cannot run management command because managed Python is missing: ${python_bin}" || return 1
    fi
    exec "$python_bin" "$MAIN_PY_PATH" "$SOAI_LAUNCHER_COMMAND" "${SOAI_PASSTHROUGH_ARGS[@]}"
}


[ -f "$MAIN_PY_PATH" ] || { echo "ERROR: Missing backend entrypoint: ${MAIN_PY_PATH}" >&2; exit 1; }
if soai_launcher__emit_information_if_requested "$@"; then
    exit 0
fi
soai_launcher__elevate_for_installed_state "$@" || exit 1
soai_launcher__recover_update_transactions || exit 1

soai_launcher__dispatch "$@"
