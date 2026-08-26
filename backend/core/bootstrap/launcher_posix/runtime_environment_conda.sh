#!/usr/bin/env bash
# SoAI - POSIX launcher Conda runtime provisioning [backend/core/bootstrap/launcher_posix/runtime_environment_conda.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

SOAI_MANAGED_RUNTIME_SETUPTOOLS_VERSION="84.0.0"

soai_managed_runtime__tls_smoke_check() {
    local env_dir="$1"
    if [ -z "$env_dir" ] || [ ! -x "${env_dir}/bin/python" ]; then
        return 0
    fi
    "${env_dir}/bin/python" -c "import ssl, urllib.request; ctx=ssl.create_default_context(); resp=urllib.request.urlopen('https://example.com', context=ctx, timeout=10); print(getattr(resp,'status',None) or 0)" >/dev/null 2>&1 || return 1
    return 0
}

soai_managed_runtime__ensure_posix_cli_dependencies() {
    local env_dir="$1"
    local state_dir="$2"
    local micromamba_version="${3:-2.5.0}"
    local offline_mode="${4:-0}"
    if [ -z "$env_dir" ] || [ ! -d "$env_dir" ]; then
        soai_managed_runtime__die "Managed env dir is missing: ${env_dir}" || return 1
    fi
    local platform
    platform="$(soai_managed_runtime__detect_platform)" || return 1
    case "$platform" in
        linux-64|linux-aarch64|osx-64|osx-arm64) ;;
        *) return 0 ;;
    esac
    local -a required_binaries=(rg sed awk grep find xargs jq curl wget ffmpeg)
    local -a missing_binaries=()
    local binary_name=""
    for binary_name in "${required_binaries[@]}"; do
        if [ ! -x "${env_dir}/bin/${binary_name}" ]; then
            missing_binaries+=("$binary_name")
        fi
    done
    if [ "${#missing_binaries[@]}" -eq 0 ]; then
        return 0
    fi
    if [ "$offline_mode" = "1" ]; then
        soai_managed_runtime__die "STAY_OFFLINE=true but POSIX CLI dependencies are missing from the managed env (${missing_binaries[*]}). Disable STAY_OFFLINE and run once online." || return 1
    fi
    local micromamba_bin
    micromamba_bin="$(soai_managed_runtime__ensure_micromamba "$state_dir" "$micromamba_version" "$offline_mode")" || return 1
    local mamba_root="${state_dir}/managed_runtime/mamba_root"
    if ! mkdir -p "$mamba_root"; then
        soai_managed_runtime__die "Failed to create mamba root: ${mamba_root}" || return 1
    fi
    if ! soai_install__run_noisy_command "${micromamba_bin}" install -y -p "$env_dir" \
            --root-prefix "$mamba_root" \
            --no-rc \
            --override-channels \
            -c conda-forge \
            ripgrep sed gawk grep findutils jq curl wget "ffmpeg=*=lgpl*"; then
        soai_managed_runtime__die "micromamba POSIX CLI dependency install failed at: ${env_dir}" || return 1
    fi
}

soai_managed_runtime__ensure_python_build_dependencies() {
    local env_dir="$1"
    local state_dir="$2"
    local micromamba_version="${3:-2.5.0}"
    local offline_mode="${4:-0}"
    if [ -z "$env_dir" ] || [ ! -x "${env_dir}/bin/python" ]; then
        soai_managed_runtime__die "Managed env python is missing for build dependency validation: ${env_dir}" || return 1
    fi
    if "${env_dir}/bin/python" -c "import pip, setuptools, wheel; raise SystemExit(0 if setuptools.__version__ == '${SOAI_MANAGED_RUNTIME_SETUPTOOLS_VERSION}' else 1)" >/dev/null 2>&1; then
        return 0
    fi
    if [ "$offline_mode" = "1" ]; then
        soai_managed_runtime__die "STAY_OFFLINE=true but managed Python build dependencies are missing from the managed env. Disable STAY_OFFLINE and run once online." || return 1
    fi
    local micromamba_bin
    micromamba_bin="$(soai_managed_runtime__ensure_micromamba "$state_dir" "$micromamba_version" "$offline_mode")" || return 1
    local mamba_root="${state_dir}/managed_runtime/mamba_root"
    if ! mkdir -p "$mamba_root"; then
        soai_managed_runtime__die "Failed to create mamba root: ${mamba_root}" || return 1
    fi
    if ! soai_install__run_noisy_command "${micromamba_bin}" install -y -p "$env_dir" \
            --root-prefix "$mamba_root" \
            --no-rc \
            --override-channels \
            -c conda-forge \
            pip "setuptools=${SOAI_MANAGED_RUNTIME_SETUPTOOLS_VERSION}" wheel; then
        soai_managed_runtime__die "micromamba Python build dependency install failed at: ${env_dir}" || return 1
    fi
}

soai_managed_runtime__env_python_matches_version() {
    local env_dir="$1"
    local python_version="$2"
    if [ -z "$env_dir" ] || [ -z "$python_version" ] || [ ! -x "${env_dir}/bin/python" ]; then
        return 1
    fi
    local expected_major="${python_version%%.*}"
    local remaining_version="${python_version#*.}"
    if [ "$remaining_version" = "$python_version" ]; then
        return 1
    fi
    local expected_minor="${remaining_version%%.*}"
    local expected_major_minor="${expected_major}.${expected_minor}"
    if [ -z "$expected_major_minor" ] || [ "$expected_major_minor" = "." ]; then
        return 1
    fi
    local actual_major_minor=""
    actual_major_minor="$("${env_dir}/bin/python" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)" || return 1
    [ "$actual_major_minor" = "$expected_major_minor" ]
}

soai_managed_runtime__remove_default_env() {
    local env_dir="$1"
    if [ -z "$env_dir" ] || [ -z "${SCRIPT_DIR:-}" ]; then
        return 1
    fi
    local env_parent=""
    env_parent="$(cd "$(dirname "$env_dir")" 2>/dev/null && pwd -P)" || return 1
    local script_root=""
    script_root="$(cd "$SCRIPT_DIR" 2>/dev/null && pwd -P)" || return 1
    local env_abs="${env_parent}/$(basename "$env_dir")"
    if [ "$env_abs" != "${script_root}/soai_main_venv" ]; then
        return 1
    fi
    rm -rf "$env_abs"
}

soai_managed_runtime_ensure_env() {
    local env_dir="$1"
    local python_version="$2"
    local state_dir="$3"
    local lock_base="$4"
    local micromamba_version="${5:-2.5.0}"
    local offline_mode="${6:-0}"
    if [ -z "$env_dir" ] || [ -z "$python_version" ] || [ -z "$state_dir" ] || [ -z "$lock_base" ]; then
        soai_managed_runtime__die "Invalid managed runtime arguments." || return 1
    fi
    if ! mkdir -p "$state_dir" "$lock_base"; then
        soai_managed_runtime__die "Failed to create managed runtime dirs." || return 1
    fi
    local lock_dir="${lock_base}/soai.managed_runtime.lock.d"
    if ! soai_managed_runtime__acquire_lock_dir "$lock_dir"; then
        return 1
    fi
    local lock_released=0
    soai_managed_runtime__release_lock_dir_once() {
        if [ "$lock_released" = "0" ]; then
            lock_released=1
            soai_managed_runtime__release_lock_dir "$lock_dir"
        fi
    }
    if soai_managed_runtime__is_conda_env_dir "$env_dir"; then
        if ! soai_managed_runtime__env_python_matches_version "$env_dir" "$python_version"; then
            if [ "$offline_mode" = "1" ]; then
                soai_managed_runtime__release_lock_dir_once
                soai_managed_runtime__die "STAY_OFFLINE=true but managed env Python version does not match ${python_version}. Disable STAY_OFFLINE and run once online." || return 1
            fi
            soai_managed_runtime__remove_default_env "$env_dir" || {
                soai_managed_runtime__release_lock_dir_once
                soai_managed_runtime__die "Managed env Python version does not match ${python_version}. Delete the stale env and re-run: ${env_dir}" || return 1
            }
        else
            soai_managed_runtime__ensure_env_uses_system_ca "$env_dir"
            soai_managed_runtime__ensure_sqlite_runtime "$env_dir" "$state_dir" "$micromamba_version" "$offline_mode" || {
                soai_managed_runtime__release_lock_dir_once
                return 1
            }
            soai_managed_runtime__ensure_posix_cli_dependencies "$env_dir" "$state_dir" "$micromamba_version" "$offline_mode" || {
                soai_managed_runtime__release_lock_dir_once
                return 1
            }
            soai_managed_runtime__ensure_tesseract "$env_dir" "$state_dir" "$micromamba_version" "$offline_mode" || {
                soai_managed_runtime__release_lock_dir_once
                return 1
            }
            soai_managed_runtime__ensure_python_build_dependencies "$env_dir" "$state_dir" "$micromamba_version" "$offline_mode" || {
                soai_managed_runtime__release_lock_dir_once
                return 1
            }
            soai_managed_runtime__release_lock_dir_once
            return 0
        fi
    fi
    if [ -e "$env_dir" ] && [ ! -d "$env_dir" ]; then
        soai_managed_runtime__release_lock_dir_once
        soai_managed_runtime__die "Environment path exists but is not a directory: ${env_dir}" || return 1
    fi
    if [ -x "${env_dir}/bin/python" ] && [ ! -d "${env_dir}/conda-meta" ]; then
        if [ "$offline_mode" != "1" ] && soai_managed_runtime__remove_default_env "$env_dir"; then
            :
        else
            soai_managed_runtime__release_lock_dir_once
            soai_managed_runtime__die "Legacy venv detected at ${env_dir}. Delete it and re-run (SoAI uses managed conda envs only)." || return 1
        fi
    fi
    if [ -d "$env_dir" ] && ! soai_managed_runtime__is_conda_env_dir "$env_dir"; then
        if [ "$offline_mode" != "1" ] && soai_managed_runtime__remove_default_env "$env_dir"; then
            :
        else
            soai_managed_runtime__release_lock_dir_once
            soai_managed_runtime__die "Invalid managed env directory detected at ${env_dir}. Delete it and re-run." || return 1
        fi
    fi
    if [ "$offline_mode" = "1" ]; then
        soai_managed_runtime__release_lock_dir_once
        soai_managed_runtime__die "STAY_OFFLINE=true but managed env is missing. Disable STAY_OFFLINE and run once online." || return 1
    fi
    local micromamba_bin
    micromamba_bin="$(soai_managed_runtime__ensure_micromamba "$state_dir" "$micromamba_version" "$offline_mode")" || {
        soai_managed_runtime__release_lock_dir_once
        return 1
    }
    local mamba_root="${state_dir}/managed_runtime/mamba_root"
    if ! mkdir -p "$mamba_root"; then
        soai_managed_runtime__release_lock_dir_once
        soai_managed_runtime__die "Failed to create mamba root: ${mamba_root}" || return 1
    fi
    if ! soai_install__run_noisy_command "${micromamba_bin}" create -y -p "$env_dir" \
            --root-prefix "$mamba_root" \
            --no-rc \
            --override-channels \
            -c conda-forge \
            "python=${python_version}" pip "setuptools=${SOAI_MANAGED_RUNTIME_SETUPTOOLS_VERSION}" wheel; then
        soai_managed_runtime__release_lock_dir_once
        soai_managed_runtime__die "micromamba env creation failed at: ${env_dir}" || return 1
    fi
    local platform
    platform="$(soai_managed_runtime__detect_platform)" || {
        soai_managed_runtime__release_lock_dir_once
        return 1
    }
    local conda_requirements_path=""
    case "$platform" in
        linux-aarch64|osx-arm64)
            conda_requirements_path="${SOAI_LAUNCHER_MODULE_DIR}/arm64_conda_runtime_packages.txt"
            ;;
        osx-64)
            conda_requirements_path="${SOAI_LAUNCHER_MODULE_DIR}/darwin_x64_conda_runtime_packages.txt"
            ;;
        *) ;;
    esac
    if [ -n "$conda_requirements_path" ]; then
        if [ ! -f "$conda_requirements_path" ]; then
            soai_managed_runtime__release_lock_dir_once
            soai_managed_runtime__die "Managed runtime conda requirements are missing: ${conda_requirements_path}" || return 1
        fi
        local -a conda_packages=()
        local conda_package=""
        while IFS= read -r conda_package || [ -n "$conda_package" ]; do
            if [ -n "$conda_package" ]; then
                conda_packages+=("$conda_package")
            fi
        done < "$conda_requirements_path"
        if [ "${#conda_packages[@]}" -eq 0 ]; then
            soai_managed_runtime__release_lock_dir_once
            soai_managed_runtime__die "Managed runtime conda requirements are empty: ${conda_requirements_path}" || return 1
        fi
        if ! soai_install__run_noisy_command "${micromamba_bin}" install -y -p "$env_dir" \
                --root-prefix "$mamba_root" \
                --no-rc \
                --override-channels \
                -c conda-forge \
                "${conda_packages[@]}"; then
            soai_managed_runtime__release_lock_dir_once
            soai_managed_runtime__die "micromamba platform runtime package install failed (${platform})." || return 1
        fi
    fi
    soai_managed_runtime__ensure_env_uses_system_ca "$env_dir"
    soai_managed_runtime__ensure_sqlite_runtime "$env_dir" "$state_dir" "$micromamba_version" "$offline_mode" || {
        soai_managed_runtime__release_lock_dir_once
        return 1
    }
    soai_managed_runtime__ensure_posix_cli_dependencies "$env_dir" "$state_dir" "$micromamba_version" "$offline_mode" || {
        soai_managed_runtime__release_lock_dir_once
        return 1
    }
    soai_managed_runtime__ensure_tesseract "$env_dir" "$state_dir" "$micromamba_version" "$offline_mode" || {
        soai_managed_runtime__release_lock_dir_once
        return 1
    }
    soai_managed_runtime__ensure_python_build_dependencies "$env_dir" "$state_dir" "$micromamba_version" "$offline_mode" || {
        soai_managed_runtime__release_lock_dir_once
        return 1
    }
    soai_managed_runtime__release_lock_dir_once
    if [ ! -x "${env_dir}/bin/python" ]; then
        soai_managed_runtime__die "Managed env is invalid: ${env_dir}/bin/python missing." || return 1
    fi
    if ! soai_managed_runtime__env_python_matches_version "$env_dir" "$python_version"; then
        soai_managed_runtime__die "Managed env is invalid: Python version does not match ${python_version}." || return 1
    fi
    if [ "$offline_mode" != "1" ]; then
        if ! soai_managed_runtime__tls_smoke_check "$env_dir"; then
            echo "WARNING: Managed env TLS verification check failed (HTTPS). If RAG/web fetching fails with CERTIFICATE_VERIFY_FAILED, set SSL_CERT_FILE to your system CA bundle." >&2
        fi
    fi
}
