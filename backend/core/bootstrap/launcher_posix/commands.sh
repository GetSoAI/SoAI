#!/usr/bin/env bash
# SoAI - POSIX launcher lifecycle command execution [backend/core/bootstrap/launcher_posix/commands.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_launcher__run_post_update_hook() {
    if [ "$SOAI_LAUNCHER_FAST_MANAGEMENT" = "1" ]; then
        return 0
    fi
    local python_bin="${SOAI_VENV_PATH}/bin/python"
    if [ ! -x "$python_bin" ]; then
        soai_managed_runtime__die "Cannot run post-update hook because managed Python is missing: ${python_bin}" || return 1
    fi
    local python_path="${SCRIPT_DIR}/backend"
    if [ -n "${PYTHONPATH:-}" ]; then
        python_path="${python_path}:${PYTHONPATH}"
    fi
    (cd "$SCRIPT_DIR" && PYTHONPATH="$python_path" "$python_bin" -m app.updater.post_update_hook)
}

soai_launcher__run_backend_install_deps() {
    local python_bin="${SOAI_VENV_PATH}/bin/python"
    "$python_bin" "$MAIN_PY_PATH" "install-deps"
}

soai_launcher__run_python_dependency_bootstrap() {
    local python_bin="${SOAI_VENV_PATH}/bin/python"
    if [ ! -x "$python_bin" ]; then
        soai_managed_runtime__die "Cannot bootstrap Python dependencies because managed Python is missing: ${python_bin}" || return 1
    fi
    (
        cd "${SCRIPT_DIR}/backend" && \
        SOAI_LOCKS_PATH="$SOAI_LOCKS_PATH" \
        SOAI_STAGE0_OFFLINE_MODE="$OFFLINE_MODE_ENABLED" \
        "$python_bin" -m core.bootstrap.python_dependencies_cli "$SCRIPT_DIR"
    )
}

soai_launcher__install_deps_emit_or_release() {
    local owns_install_lock="$1"
    shift
    soai_install__emit_stage "$@" && return 0
    soai_launcher__release_install_deps_lock "$owns_install_lock"
    return 1
}

soai_launcher__release_install_deps_lock() {
    local owns_install_lock="$1"
    if [ "$owns_install_lock" = "1" ]; then
        soai_install__release_install_lock
    fi
}

soai_launcher__install_deps_fail() {
    local owns_install_lock="$1"
    local operation_root="$2"
    local stage="$3"
    local message="$4"
    soai_install__emit_stage "$operation_root" "install-deps" "$stage" "failed" "$message" || true
    soai_launcher__release_install_deps_lock "$owns_install_lock"
    return 1
}

soai_launcher__install_deps() {
    local operation_root="$SCRIPT_DIR"
    local owns_install_lock=0
    local install_lock_dir="${SOAI_LOCKS_PATH}/soai.install.lock.d"
    if [ "${SOAI_INSTALL_LOCK_HELD_PATH:-}" != "$install_lock_dir" ] \
        || ! soai_managed_runtime__lock_dir_is_process_owned "$install_lock_dir" "$PPID"; then
        soai_install__acquire_install_lock "$operation_root" || return 1
        owns_install_lock=1
    fi
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "preflight" "started" "Checking SoAI runtime state..." || return 1
    if soai_managed_runtime__lock_dir_has_live_owner "${SOAI_LOCKS_PATH}/soai.runtime.lock.d" || soai_install__target_running "$SCRIPT_DIR"; then
        soai_launcher__install_deps_fail "$owns_install_lock" "$operation_root" "preflight" "Refusing to install dependencies while SoAI is starting or running." || return 1
    fi
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "preflight" "completed" "SoAI is not running." || return 1
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "managed-runtime" "started" "Preparing SoAI managed runtime..." || return 1
    if ! soai_launcher__prepare_runtime; then
        soai_launcher__install_deps_fail "$owns_install_lock" "$operation_root" "managed-runtime" "SoAI managed runtime preparation failed." || return 1
    fi
    if ! soai_launcher__run_python_dependency_bootstrap; then
        soai_launcher__install_deps_fail "$owns_install_lock" "$operation_root" "managed-runtime" "SoAI managed runtime preparation failed." || return 1
    fi
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "managed-runtime" "completed" "SoAI managed runtime is ready." || return 1
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "soaibench-opencl" "started" "Checking optional SoAIBench OpenCL packages..." || return 1
    soai_launcher__provision_soaibench_opencl
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "soaibench-opencl" "completed" "Optional SoAIBench OpenCL package check completed." || return 1
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "runtime-artifacts" "started" "Provisioning SoAI runtime artifacts..." || return 1
    if ! soai_launcher__run_backend_install_deps; then
        soai_launcher__install_deps_fail "$owns_install_lock" "$operation_root" "runtime-artifacts" "SoAI runtime artifact provisioning failed." || return 1
    fi
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "runtime-artifacts" "completed" "SoAI runtime artifacts are ready." || return 1
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "migration-hook" "started" "Running SoAI V1 post-install migration hook..." || return 1
    if ! soai_launcher__run_post_update_hook; then
        soai_launcher__install_deps_fail "$owns_install_lock" "$operation_root" "migration-hook" "SoAI V1 post-install migration hook failed." || return 1
    fi
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "migration-hook" "completed" "SoAI V1 post-install migration hook completed." || return 1
    soai_launcher__install_deps_emit_or_release "$owns_install_lock" "$operation_root" "install-deps" "complete" "completed" "SoAI dependency installation completed successfully." || return 1
    soai_launcher__release_install_deps_lock "$owns_install_lock"
}

soai_launcher__run_mcp_stdio() {
    exec 3>&1
    {
        soai_managed_runtime__wait_for_lock_dir_clear "${SOAI_LOCKS_PATH}/soai.install.lock.d"
        soai_launcher__prepare_runtime || return 1
        soai_launcher__run_python_dependency_bootstrap || return 1
    } >&2
    local python_path="${SCRIPT_DIR}/backend"
    if [ -n "${PYTHONPATH:-}" ]; then
        python_path="${python_path}:${PYTHONPATH}"
    fi
    cd "$SCRIPT_DIR"
    PYTHONPATH="$python_path" exec "${SOAI_VENV_PATH}/bin/python" -m app.mcp_stdio_proxy 1>&3 3>&-
}

soai_launcher__dispatch() {
    if soai_launcher__emit_information_if_requested "$@"; then
        return 0
    fi
    soai_launcher__parse_args "$@"
    soai_launcher__configure_paths
    case "$SOAI_LAUNCHER_COMMAND" in
        install)
            soai_install__install_to_target "$SOAI_INSTALL_TARGET" "${SOAI_PASSTHROUGH_ARGS[@]}"
            ;;
        install-deps)
            soai_launcher__install_deps
            ;;
        mcp-stdio)
            soai_launcher__run_mcp_stdio
            ;;
        status|stop|restart)
            soai_launcher__run_management
            ;;
        *)
            soai_launcher__run_start
            ;;
    esac
}
