#!/usr/bin/env bash
# SoAI - POSIX launcher installation target resolution [backend/core/bootstrap/launcher_posix/install_target.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_install__default_target() {
    case "$(uname -s 2>/dev/null || true)" in
        Darwin) printf "/Applications/SoAI" ;;
        *) printf "/opt/soai" ;;
    esac
}

soai_install__recognizable_target() {
    local target="$1"
    if [ ! -e "$target" ]; then
        return 0
    fi
    if [ ! -d "$target" ]; then
        return 1
    fi
    if [ -z "$(find "$target" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
        return 0
    fi
    if [ -f "${target}/.soai_install_manifest.json" ]; then
        return 0
    fi
    if [ -f "${target}/.soai_install_in_progress" ]; then
        return 0
    fi
    if [ -f "${target}/${SOAI_EXPLICIT_ENTRYPOINT_RELATIVE_PATH}" ] \
        && [ -f "${target}/${SOAI_EXPLICIT_LAUNCHER_RELATIVE_PATH}" ]; then
        return 0
    fi
    return 1
}

soai_install__validate_target_path() {
    local target="$1"
    local parent_dir
    parent_dir="$(dirname "$target")"
    if [ -L "$target" ]; then
        soai_managed_runtime__die "Install target must not be a symlink: ${target}" || return 1
    fi
    if [ ! -d "$parent_dir" ]; then
        soai_managed_runtime__die "Install target parent directory does not exist: ${parent_dir}" || return 1
    fi
    if [ -e "$target" ]; then
        if [ ! -w "$target" ]; then
            soai_managed_runtime__die "Install target is not writable: ${target}" || return 1
        fi
        return 0
    fi
    if [ ! -w "$parent_dir" ]; then
        soai_managed_runtime__die "Install target parent directory is not writable: ${parent_dir}" || return 1
    fi
}

soai_install__target_running() {
    local target="$1"
    local temp_dir
    temp_dir="$(soai_install__target_temp_dir "$target")"
    local pid_file="${temp_dir}/soai.pid"
    local python_executable="${target}/soai_main_venv/bin/python"
    if [ ! -f "$pid_file" ] || [ ! -x "$python_executable" ]; then
        return 1
    fi
    "$python_executable" -c 'import json,os,sys,psutil,uuid; record=json.load(open(sys.argv[1],encoding="utf-8")); assert set(record)=={"schema_version","runtime_id","edition","pid","process_create_time_ns","base_dir","started_at_epoch_ms","api_endpoint"} and record["schema_version"]==1 and record["edition"]==sys.argv[3] and str(uuid.UUID(record["runtime_id"]))==record["runtime_id"] and os.path.normcase(os.path.realpath(record["base_dir"]))==os.path.normcase(os.path.realpath(sys.argv[2])); process=psutil.Process(record["pid"]); assert process.is_running() and int(round(process.create_time()*1000000000))==record["process_create_time_ns"]' "$pid_file" "$target" "$SOAI_EXPLICIT_EDITION" >/dev/null 2>&1
}

soai_install__target_config_path_value() {
    local config_path="$1"
    local key="$2"
    awk -v wanted_key="$key" '
        /^[[:space:]]*($|#)/ { next }
        {
            match($0, /^[[:space:]]*/)
            indent = RLENGTH
            line = $0
            sub(/^[[:space:]]*/, "", line)
            if (line ~ /^SYSTEM:[[:space:]]*$/) {
                in_system = 1
                in_paths = 0
                system_indent = indent
                next
            }
            if (in_system && indent <= system_indent && line !~ /^SYSTEM:[[:space:]]*$/) {
                in_system = 0
                in_paths = 0
            }
            if (in_system && line ~ /^PATHS:[[:space:]]*$/) {
                in_paths = 1
                paths_indent = indent
                next
            }
            if (in_paths && indent <= paths_indent && line !~ /^PATHS:[[:space:]]*$/) {
                in_paths = 0
            }
            if (in_paths && index(line, wanted_key ":") == 1) {
                sub("^[^:]+:[[:space:]]*", "", line)
                sub(/[[:space:]]#.*$/, "", line)
                sub(/^[[:space:]]*/, "", line)
                sub(/[[:space:]]*$/, "", line)
                sub(/^'\''/, "", line)
                sub(/'\''$/, "", line)
                sub(/^"/, "", line)
                sub(/"$/, "", line)
                print line
                exit
            }
        }
    ' "$config_path" 2>/dev/null || true
}

soai_install__target_temp_dir() {
    local target="$1"
    local config_path="${target}/data/config/config.yaml"
    local default_temp="${target}/data/temp"
    if [ ! -f "$config_path" ]; then
        printf "%s" "$default_temp"
        return
    fi
    local system_data_value
    local system_data_dir
    system_data_value="$(soai_install__target_config_path_value "$config_path" "SYSTEM_DATA")"
    if [ -z "$system_data_value" ]; then
        system_data_value="data"
    fi
    case "$system_data_value" in
        /*) system_data_dir="$system_data_value" ;;
        *) system_data_dir="${target}/${system_data_value}" ;;
    esac
    local temp_value
    temp_value="$(soai_install__target_config_path_value "$config_path" "TEMP")"
    if [ -z "$temp_value" ]; then
        printf "%s" "$default_temp"
        return
    fi
    case "$temp_value" in
        /*) printf "%s" "$temp_value" ;;
        *) printf "%s/%s" "$system_data_dir" "$temp_value" ;;
    esac
}

soai_install__acquire_install_lock() {
    local target="$1"
    local lock_base="${target}/data/state/locks"
    if ! mkdir -p "$lock_base"; then
        soai_managed_runtime__die "Failed to create install lock directory: ${lock_base}" || return 1
    fi
    SOAI_INSTALL_LOCK_DIR="${lock_base}/soai.install.lock.d"
    soai_managed_runtime__acquire_lock_dir "$SOAI_INSTALL_LOCK_DIR"
}

soai_install__release_install_lock() {
    if [ -n "${SOAI_INSTALL_LOCK_DIR:-}" ]; then
        soai_managed_runtime__release_lock_dir "$SOAI_INSTALL_LOCK_DIR"
        SOAI_INSTALL_LOCK_DIR=""
    fi
}
