#!/usr/bin/env bash
# SoAI - POSIX launcher CLI usage text [backend/core/bootstrap/launcher_posix/cli_information.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_launcher__print_help() {
    cat <<'EOF'
usage: soai [COMMAND] [OPTIONS]

SoAI Main Application and Management Utility.

commands:
  start                 Start SoAI (default).
  status                Print the status of the running SoAI instance and exit.
  stop                  Send a stop signal to the running SoAI instance and exit.
  restart               Send a restart signal to the running SoAI instance and exit.
  install-deps          Provision SoAI runtime dependencies and exit.
  install               Install SoAI to the configured target.
  mcp-stdio             Run the MCP stdio proxy.

options:
  -h, --help            Print this help message and exit.
  -version, --version   Print the SoAI backend version and exit.
  --start-no-browser    Prevent automatic browser opening on startup.
  --verbose             Enable verbose bootstrap logging output.
  --reset-user-password USERNAME
                        Run the password reset utility for the specified user and exit.
EOF
}

soai_launcher__read_backend_version() {
    local version_file="${SCRIPT_DIR}/VERSION"
    local version_value=""
    if [ -f "$version_file" ]; then
        IFS= read -r version_value < "$version_file" || true
    fi
    if ! printf '%s' "$version_value" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
        soai_managed_runtime__die "Cannot read SoAI backend version from ${version_file}." || return 1
    fi
    printf "%s" "$version_value"
}

soai_launcher__print_version() {
    local version_value=""
    version_value="$(soai_launcher__read_backend_version)" || return 1
    printf "SoAI %s\n" "$version_value"
}

soai_launcher__emit_information_if_requested() {
    local soai_launcher_arg=""
    for soai_launcher_arg in "$@"; do
        case "$soai_launcher_arg" in
            -h|--help|help)
                soai_launcher__print_help
                return 0
                ;;
            *) ;;
        esac
    done
    for soai_launcher_arg in "$@"; do
        case "$soai_launcher_arg" in
            -version|--version|version)
                soai_launcher__print_version
                return 0
                ;;
            *) ;;
        esac
    done
    return 1
}
