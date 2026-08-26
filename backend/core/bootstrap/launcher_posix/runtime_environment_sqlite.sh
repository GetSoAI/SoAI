#!/usr/bin/env bash
# SoAI - POSIX launcher managed SQLite provisioning [backend/core/bootstrap/launcher_posix/runtime_environment_sqlite.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

SOAI_MANAGED_SQLITE_VERSION="3.53.3"
SOAI_MINIMUM_SAFE_SQLITE_VERSION="3.51.3"

soai_managed_runtime__python_sqlite_version() {
    local environment_directory="$1"
    "${environment_directory}/bin/python" -c "import sqlite3; print(sqlite3.sqlite_version)" 2>/dev/null
}

soai_managed_runtime__sqlite_cli_version() {
    local environment_directory="$1"
    if [ ! -x "${environment_directory}/bin/sqlite3" ]; then
        return 1
    fi
    "${environment_directory}/bin/sqlite3" --version 2>/dev/null | awk '{print $1}'
}

soai_managed_runtime__sqlite_runtime_matches() {
    local environment_directory="$1"
    local python_sqlite_version=""
    local sqlite_cli_version=""
    python_sqlite_version="$(soai_managed_runtime__python_sqlite_version "$environment_directory")" || return 1
    sqlite_cli_version="$(soai_managed_runtime__sqlite_cli_version "$environment_directory")" || return 1
    [ "$python_sqlite_version" = "$SOAI_MANAGED_SQLITE_VERSION" ] \
        && [ "$sqlite_cli_version" = "$SOAI_MANAGED_SQLITE_VERSION" ]
}

soai_managed_runtime__ensure_sqlite_runtime() {
    local environment_directory="$1"
    local state_directory="$2"
    local micromamba_version="${3:-2.5.0}"
    local offline_mode="${4:-0}"
    if [ -z "$environment_directory" ] || [ ! -x "${environment_directory}/bin/python" ]; then
        soai_managed_runtime__die "Managed Python is missing for SQLite runtime validation: ${environment_directory}" || return 1
    fi
    if soai_managed_runtime__sqlite_runtime_matches "$environment_directory"; then
        return 0
    fi
    if [ "$offline_mode" = "1" ]; then
        soai_managed_runtime__die "STAY_OFFLINE=true but managed SQLite ${SOAI_MANAGED_SQLITE_VERSION} is unavailable. SQLite ${SOAI_MINIMUM_SAFE_SQLITE_VERSION} or newer is required for safe WAL access. Disable STAY_OFFLINE and run once online." || return 1
    fi
    local micromamba_binary=""
    micromamba_binary="$(soai_managed_runtime__ensure_micromamba "$state_directory" "$micromamba_version" "$offline_mode")" || return 1
    local mamba_root="${state_directory}/managed_runtime/mamba_root"
    if ! mkdir -p "$mamba_root"; then
        soai_managed_runtime__die "Failed to create mamba root: ${mamba_root}" || return 1
    fi
    if ! soai_install__run_noisy_command "${micromamba_binary}" install -y -p "$environment_directory" \
            --root-prefix "$mamba_root" \
            --no-rc \
            --override-channels \
            -c conda-forge \
            "sqlite=${SOAI_MANAGED_SQLITE_VERSION}"; then
        soai_managed_runtime__die "Managed SQLite ${SOAI_MANAGED_SQLITE_VERSION} installation failed at: ${environment_directory}" || return 1
    fi
    if ! soai_managed_runtime__sqlite_runtime_matches "$environment_directory"; then
        soai_managed_runtime__die "Managed SQLite installation completed without the required Python library and CLI version ${SOAI_MANAGED_SQLITE_VERSION}." || return 1
    fi
}
