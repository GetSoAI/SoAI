#!/usr/bin/env bash
# SoAI - POSIX launcher command argument validation [backend/core/bootstrap/launcher_posix/command_arguments.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_launcher__require_option_value() {
    local option="$1"
    local value="$2"
    if [ -z "$value" ]; then
        soai_managed_runtime__die "${option} requires a non-empty value." || return 1
    fi
    soai_install__reject_control_chars "$option" "$value" || return 1
}

soai_launcher__normalize_status_file() {
    local status_file="$1"
    soai_launcher__require_option_value "--status-file" "$status_file" || return 1
    case "$status_file" in
        /*) printf "%s" "$status_file" ;;
        *) printf "%s/%s" "$(pwd -P)" "$status_file" ;;
    esac
}

soai_launcher__normalize_command() {
    case "${1:-start}" in
        install|--install|-install) printf "install" ;;
        install-deps|--install-deps|-install-deps) printf "install-deps" ;;
        mcp-stdio|--mcp-stdio|-mcp-stdio) printf "mcp-stdio" ;;
        start|--start|-start|"") printf "start" ;;
        status|--status|-status) printf "status" ;;
        stop|--stop|-stop) printf "stop" ;;
        restart|--restart|-restart) printf "restart" ;;
        *) printf "start" ;;
    esac
}

soai_launcher__parse_args() {
    SOAI_LAUNCHER_COMMAND="start"
    SOAI_INSTALL_TARGET=""
    SOAI_INSTALL_SILENT=0
    SOAI_INSTALL_FAST=0
    SOAI_INSTALL_DEFER_SERVICE_START=0
    SOAI_LAUNCHER_COMMAND_SET=0
    SOAI_INSTALL_TARGET_EXPLICIT=0
    SOAI_INSTALL_OPTIONS_USED=0
    SOAI_PASSTHROUGH_ARGS=()
    while [ "$#" -gt 0 ]; do
        case "$1" in
            install|--install|-install|install-deps|--install-deps|-install-deps|mcp-stdio|--mcp-stdio|-mcp-stdio|start|--start|-start|status|--status|-status|stop|--stop|-stop|restart|--restart|-restart)
                if [ "$SOAI_LAUNCHER_COMMAND_SET" = "1" ]; then
                    soai_managed_runtime__die "Only one SoAI launcher command can be specified." || return 1
                fi
                SOAI_LAUNCHER_COMMAND_SET=1
                SOAI_LAUNCHER_COMMAND="$(soai_launcher__normalize_command "$1")"
                shift
                ;;
            --target|-target)
                if [ "$#" -lt 2 ]; then
                    soai_managed_runtime__die "--target requires a non-empty value." || return 1
                fi
                soai_launcher__require_option_value "--target" "${2:-}" || return 1
                SOAI_INSTALL_TARGET="${2:-}"
                SOAI_INSTALL_TARGET_EXPLICIT=1
                SOAI_INSTALL_OPTIONS_USED=1
                shift 2
                ;;
            --target=*)
                soai_launcher__require_option_value "--target" "${1#--target=}" || return 1
                SOAI_INSTALL_TARGET="${1#--target=}"
                SOAI_INSTALL_TARGET_EXPLICIT=1
                SOAI_INSTALL_OPTIONS_USED=1
                shift
                ;;
            --silent|-silent)
                SOAI_INSTALL_SILENT=1
                SOAI_INSTALL_OPTIONS_USED=1
                shift
                ;;
            --fast|-fast)
                SOAI_INSTALL_FAST=1
                SOAI_INSTALL_OPTIONS_USED=1
                if [ "$SOAI_LAUNCHER_COMMAND_SET" = "0" ]; then
                    SOAI_LAUNCHER_COMMAND_SET=1
                    SOAI_LAUNCHER_COMMAND="install"
                fi
                shift
                ;;
            --defer-service-start|-defer-service-start)
                SOAI_INSTALL_DEFER_SERVICE_START=1
                SOAI_INSTALL_OPTIONS_USED=1
                shift
                ;;
            --json-events|-json-events)
                SOAI_INSTALL_JSON_EVENTS=1
                SOAI_INSTALL_OPTIONS_USED=1
                shift
                ;;
            --status-file|-status-file)
                if [ "$#" -lt 2 ]; then
                    soai_managed_runtime__die "--status-file requires a non-empty value." || return 1
                fi
                SOAI_INSTALL_STATUS_FILE="$(soai_launcher__normalize_status_file "${2:-}")" || return 1
                SOAI_INSTALL_OPTIONS_USED=1
                shift 2
                ;;
            --status-file=*)
                SOAI_INSTALL_STATUS_FILE="$(soai_launcher__normalize_status_file "${1#--status-file=}")" || return 1
                SOAI_INSTALL_OPTIONS_USED=1
                shift
                ;;
            *)
                SOAI_PASSTHROUGH_ARGS+=("$1")
                shift
                ;;
        esac
    done
    if [ -z "$SOAI_INSTALL_TARGET" ]; then
        SOAI_INSTALL_TARGET="$(soai_install__default_target)"
    fi
    if [ "${SOAI_INSTALL_FAST:-0}" = "1" ]; then
        SOAI_INSTALL_TARGET="$(soai_install__default_target)"
    fi
    if [ "$SOAI_LAUNCHER_COMMAND" != "install" ] && [ "$SOAI_LAUNCHER_COMMAND" != "install-deps" ] && [ "$SOAI_INSTALL_OPTIONS_USED" = "1" ]; then
        soai_managed_runtime__die "Install options require the install or install-deps command." || return 1
    fi
    if [ "$SOAI_LAUNCHER_COMMAND" = "install-deps" ] && [ "$SOAI_INSTALL_TARGET_EXPLICIT" = "1" ]; then
        soai_managed_runtime__die "--target is only valid with the install command." || return 1
    fi
    if [ "$SOAI_LAUNCHER_COMMAND" != "install" ] && [ "${SOAI_INSTALL_FAST:-0}" = "1" ]; then
        soai_managed_runtime__die "--fast is only valid with the install command." || return 1
    fi
    if [ "${SOAI_INSTALL_DEFER_SERVICE_START:-0}" = "1" ] \
        && { [ "$SOAI_LAUNCHER_COMMAND" != "install" ] || [ "${SOAI_INSTALL_FAST:-0}" != "1" ]; }; then
        soai_managed_runtime__die "--defer-service-start requires install --fast." || return 1
    fi
    if [ "$SOAI_LAUNCHER_COMMAND" = "status" ] || [ "$SOAI_LAUNCHER_COMMAND" = "stop" ] || [ "$SOAI_LAUNCHER_COMMAND" = "restart" ]; then
        SOAI_LAUNCHER_FAST_MANAGEMENT=1
    fi
}
