#!/usr/bin/env bash
# SoAI - POSIX launcher installation status reporting [backend/core/bootstrap/launcher_posix/install_status.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

SOAI_INSTALL_JSON_EVENTS=0
SOAI_INSTALL_STATUS_FILE=""
SOAI_INSTALL_OPERATION_ID=""
SOAI_INSTALL_COMPLETED_STAGES=""

soai_install__utc_now() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
}

soai_install__operation_id() {
    if [ -z "$SOAI_INSTALL_OPERATION_ID" ]; then
        SOAI_INSTALL_OPERATION_ID="soai-install-$(date -u '+%Y%m%dT%H%M%SZ')-$$"
    fi
    printf "%s" "$SOAI_INSTALL_OPERATION_ID"
}

soai_install__json_escape() {
    printf "%s" "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/	/\\t/g'
}

soai_install__reject_control_chars() {
    local label="$1"
    local value="$2"
    case "$value" in
        *$'\n'*|*$'\r'*|*$'\t'*)
            soai_managed_runtime__die "${label} must not contain control characters." || return 1
            ;;
        *) ;;
    esac
}

soai_install__run_noisy_command() {
    if [ "$SOAI_INSTALL_JSON_EVENTS" = "1" ] || [ "${SOAI_INSTALL_SILENT:-0}" = "1" ]; then
        "$@" >&2
        return
    fi
    "$@"
}

soai_install__completed_json() {
    local payload=""
    local stage=""
    for stage in $SOAI_INSTALL_COMPLETED_STAGES; do
        if [ -n "$payload" ]; then
            payload="${payload},"
        fi
        payload="${payload}\"$(soai_install__json_escape "$stage")\""
    done
    printf "[%s]" "$payload"
}

soai_install__default_status_file() {
    local base_dir="$1"
    printf "%s" "${base_dir}/data/state/install-status.json"
}

soai_install__write_status() {
    local install_root="$1"
    local operation="$2"
    local stage="$3"
    local state="$4"
    local message="$5"
    local path="$SOAI_INSTALL_STATUS_FILE"
    if [ -z "$path" ]; then
        path="$(soai_install__default_status_file "$install_root")"
    fi
    local parent_dir
    parent_dir="$(dirname "$path")"
    if ! mkdir -p "$parent_dir"; then
        soai_managed_runtime__die "Failed to create install status directory: ${parent_dir}" || return 1
    fi
    local tmp_path="${path}.$$.$RANDOM.tmp"
    local timestamp
    timestamp="$(soai_install__utc_now)"
    local escaped_message
    escaped_message="$(soai_install__json_escape "$message")"
    local escaped_stage
    escaped_stage="$(soai_install__json_escape "$stage")"
    local escaped_operation
    escaped_operation="$(soai_install__json_escape "$operation")"
    local escaped_operation_id
    escaped_operation_id="$(soai_install__json_escape "$(soai_install__operation_id)")"
    local completed_json
    completed_json="$(soai_install__completed_json)"
    if ! cat > "$tmp_path" <<STATUS_JSON
{
  "schema_version": 1,
  "operation_id": "${escaped_operation_id}",
  "operation": "${escaped_operation}",
  "stage": "${escaped_stage}",
  "state": "${state}",
  "message": "${escaped_message}",
  "completed_stages": ${completed_json},
  "timestamp": "${timestamp}"
}
STATUS_JSON
    then
        soai_managed_runtime__die "Failed to write install status file: ${tmp_path}" || return 1
    fi
    mv -f "$tmp_path" "$path" || return 1
}

soai_install__emit_stage() {
    local install_root="$1"
    local operation="$2"
    local stage="$3"
    local state="$4"
    local message="$5"
    if [ "$state" = "completed" ]; then
        case " $SOAI_INSTALL_COMPLETED_STAGES " in
            *" $stage "*) ;;
            *) SOAI_INSTALL_COMPLETED_STAGES="${SOAI_INSTALL_COMPLETED_STAGES} ${stage}" ;;
        esac
    fi
    soai_install__write_status "$install_root" "$operation" "$stage" "$state" "$message" || return 1
    if [ "$SOAI_INSTALL_JSON_EVENTS" = "1" ]; then
        local timestamp
        timestamp="$(soai_install__utc_now)"
        printf '{"schema_version":1,"event_type":"soai.install.stage","operation_id":"%s","operation":"%s","stage":"%s","state":"%s","message":"%s","timestamp":"%s"}\n' \
            "$(soai_install__json_escape "$(soai_install__operation_id)")" \
            "$(soai_install__json_escape "$operation")" \
            "$(soai_install__json_escape "$stage")" \
            "$state" \
            "$(soai_install__json_escape "$message")" \
            "$timestamp" || return 1
    elif [ "${SOAI_INSTALL_SILENT:-0}" != "1" ]; then
        soai_launcher__info "$message"
    fi
}
