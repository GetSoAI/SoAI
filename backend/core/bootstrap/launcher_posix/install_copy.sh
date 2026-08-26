#!/usr/bin/env bash
# SoAI - POSIX launcher installation copy operations [backend/core/bootstrap/launcher_posix/install_copy.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_install__validate_existing_manifest_edition() {
    local target="$1"
    local manifest_path="${target}/.soai_install_manifest.json"
    if [ -L "$manifest_path" ]; then
        soai_managed_runtime__die "Existing SoAI install manifest must not be a symbolic link: ${manifest_path}" || return 1
    fi
    if [ ! -f "$manifest_path" ]; then
        if [ -d "${target}/soai_os" ] && [ "$SOAI_EXPLICIT_EDITION" != "soai-os" ]; then
            soai_managed_runtime__die "Existing SoAI OS target cannot be installed as ${SOAI_EXPLICIT_EDITION}: ${target}" || return 1
        fi
        return 0
    fi
    local python_executable=""
    if [ -x "${target}/soai_main_venv/bin/python" ]; then
        python_executable="${target}/soai_main_venv/bin/python"
    elif [ -x "${SOAI_EXPLICIT_ROOT}/soai_main_venv/bin/python" ]; then
        python_executable="${SOAI_EXPLICIT_ROOT}/soai_main_venv/bin/python"
    else
        python_executable="$(command -v python3 || true)"
    fi
    if [ -z "$python_executable" ]; then
        soai_managed_runtime__die "Python 3 is required to validate the existing SoAI install edition." || return 1
    fi
    if ! "$python_executable" -c 'import json,sys; payload=json.load(open(sys.argv[1],encoding="utf-8")); assert isinstance(payload,dict) and payload.get("schema_version")==1 and payload.get("product")=="SoAI" and payload.get("edition") in {"soai-core","soai-os"} and payload.get("edition")==sys.argv[2]' "$manifest_path" "$SOAI_EXPLICIT_EDITION" 2>/dev/null; then
        soai_managed_runtime__die "Existing SoAI install edition does not match requested edition ${SOAI_EXPLICIT_EDITION}: ${target}" || return 1
    fi
}

soai_install__write_manifest() {
    local target="$1"
    local source="$2"
    local tmp_path="${target}/.soai_install_manifest.json.$$.$RANDOM.tmp"
    local timestamp
    timestamp="$(soai_install__utc_now)"
    if ! cat > "$tmp_path" <<MANIFEST_JSON
{
  "schema_version": 1,
  "product": "SoAI",
  "edition": "$(soai_install__json_escape "$SOAI_EXPLICIT_EDITION")",
  "version": "$(soai_install__json_escape "$SOAI_EXPLICIT_PRODUCT_VERSION")",
  "core_version": "$(soai_install__json_escape "$SOAI_EXPLICIT_CORE_VERSION")",
  "installed_at": "${timestamp}",
  "source": "$(soai_install__json_escape "$source")",
  "target": "$(soai_install__json_escape "$target")"
}
MANIFEST_JSON
    then
        soai_managed_runtime__die "Failed to write install manifest: ${tmp_path}" || return 1
    fi
    mv -f "$tmp_path" "${target}/.soai_install_manifest.json" || return 1
    rm -f "${target}/.soai_install_in_progress" || return 1
}

soai_install__write_in_progress_marker() {
    local target="$1"
    printf "%s\n" "$(soai_install__utc_now)" > "${target}/.soai_install_in_progress" || return 1
}

soai_install__clear_in_progress_marker() {
    local target="$1"
    rm -f "${target}/.soai_install_in_progress" || true
}

soai_install__run_target_install_deps() {
    local target="$1"
    shift
    local -a args=("install-deps")
    if [ "$SOAI_INSTALL_JSON_EVENTS" = "1" ]; then
        args+=("--json-events")
    fi
    if [ -n "$SOAI_INSTALL_STATUS_FILE" ]; then
        args+=("--status-file" "$SOAI_INSTALL_STATUS_FILE")
    fi
    if [ "${SOAI_INSTALL_SILENT:-0}" = "1" ]; then
        args+=("--silent")
    fi
    SOAI_INSTALL_LOCK_HELD_PATH="$SOAI_INSTALL_LOCK_DIR" \
        "${target}/${SOAI_EXPLICIT_LAUNCHER_RELATIVE_PATH}" "${args[@]}" "$@"
}

soai_install__install_to_target() {
    local target="$1"
    shift
    local target_name
    target_name="$(basename "$target")"
    if [ "$target_name" = "." ] || [ "$target_name" = ".." ] || [ "$target_name" = "/" ] || [ -z "$target_name" ]; then
        soai_managed_runtime__die "Install target must name a concrete SoAI directory: ${target}" || return 1
    fi
    soai_install__reject_control_chars "--target" "$target" || return 1
    local target_parent
    target_parent="$(dirname "$target")"
    if ! mkdir -p "$target_parent"; then
        soai_managed_runtime__die "Failed to create install target parent directory: ${target_parent}" || return 1
    fi
    target="$(cd "$target_parent" && printf "%s/%s" "$(pwd -P)" "$target_name")"
    soai_install__validate_target_path "$target" || return 1
    if ! soai_install__recognizable_target "$target"; then
        soai_managed_runtime__die "Install target exists but is not an empty or recognizable SoAI directory: ${target}" || return 1
    fi
    soai_install__acquire_install_lock "$target" || return 1
    if soai_managed_runtime__lock_dir_has_live_owner "${target}/data/state/locks/soai.runtime.lock.d"; then
        soai_install__release_install_lock
        soai_managed_runtime__die "Refusing to update target while SoAI is starting or running: ${target}" || return 1
    fi
    if soai_install__target_running "$target"; then
        soai_install__release_install_lock
        soai_managed_runtime__die "Refusing to update target while SoAI is running: ${target}" || return 1
    fi
    if ! soai_install__validate_existing_manifest_edition "$target"; then
        soai_install__release_install_lock
        return 1
    fi
    soai_install__write_in_progress_marker "$target" || {
        soai_install__release_install_lock
        return 1
    }
    soai_install__emit_stage "$target" "install" "copy" "started" "Installing SoAI application files to ${target}..." || {
        soai_install__clear_in_progress_marker "$target"
        soai_install__release_install_lock
        return 1
    }
    if ! soai_install__copy_tree "$SCRIPT_DIR" "$target"; then
        soai_install__emit_stage "$target" "install" "copy" "failed" "SoAI application file install failed for ${target}." || true
        soai_install__clear_in_progress_marker "$target"
        soai_install__release_install_lock
        return 1
    fi
    soai_install__emit_stage "$target" "install" "copy" "completed" "SoAI application files are installed at ${target}." || {
        soai_install__clear_in_progress_marker "$target"
        soai_install__release_install_lock
        return 1
    }
    soai_install__emit_stage "$target" "install" "dependencies" "started" "Provisioning SoAI runtime dependencies in ${target}..." || {
        soai_install__clear_in_progress_marker "$target"
        soai_install__release_install_lock
        return 1
    }
    if ! soai_install__run_target_install_deps "$target" "$@"; then
        soai_install__emit_stage "$target" "install" "dependencies" "failed" "SoAI runtime dependency provisioning failed in ${target}." || true
        soai_install__clear_in_progress_marker "$target"
        soai_install__release_install_lock
        return 1
    fi
    soai_install__emit_stage "$target" "install" "dependencies" "completed" "SoAI runtime dependencies are ready in ${target}." || {
        soai_install__clear_in_progress_marker "$target"
        soai_install__release_install_lock
        return 1
    }
    soai_install__write_manifest "$target" "$SCRIPT_DIR" || {
        soai_install__clear_in_progress_marker "$target"
        soai_install__release_install_lock
        return 1
    }
    soai_install__release_install_lock
    if [ "${SOAI_INSTALL_FAST:-0}" = "1" ]; then
        if ! soai_install__post_install_fast "$target"; then
            return 1
        fi
    fi
    soai_install__emit_stage "$target" "install" "complete" "completed" "SoAI install completed successfully at ${target}." || {
        return 1
    }
}
