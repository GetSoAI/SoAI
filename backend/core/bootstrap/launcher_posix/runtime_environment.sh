#!/usr/bin/env bash
# SoAI - POSIX launcher managed runtime selection [backend/core/bootstrap/launcher_posix/runtime_environment.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_managed_runtime__detect_platform() {
    local uname_s
    local uname_m
    uname_s="$(uname -s 2>/dev/null || true)"
    uname_m="$(uname -m 2>/dev/null || true)"
    case "${uname_s}:${uname_m}" in
        Linux:x86_64|Linux:amd64) printf "linux-64" ;;
        Linux:aarch64|Linux:arm64) printf "linux-aarch64" ;;
        Darwin:x86_64) printf "osx-64" ;;
        Darwin:arm64) printf "osx-arm64" ;;
        *) soai_managed_runtime__die "Unsupported platform: ${uname_s} ${uname_m}" || return 1 ;;
    esac
}

soai_managed_runtime__read_stay_offline() {
    local config_path="$1"
    if [ -z "$config_path" ] || [ ! -f "$config_path" ]; then
        printf "0"
        return
    fi
    local offline_value
    offline_value=$(
        grep -E "^[[:space:]]*STAY_OFFLINE[[:space:]]*:" "$config_path" 2>/dev/null \
            | head -1 \
            | cut -d':' -f2- \
            | tr -d "[:space:]\"'" \
            | tr '[:upper:]' '[:lower:]' \
            || true
    )
    case "$offline_value" in
        true|1|yes|on) printf "1" ;;
        *) printf "0" ;;
    esac
}

soai_managed_runtime__build_system_ca_bundle() {
    local output_path="$1"
    if [ -z "$output_path" ]; then
        return 1
    fi
    local source_dir="/etc/ssl/certs"
    if [ ! -d "$source_dir" ]; then
        return 1
    fi
    local tmp_file=""
    tmp_file="$(mktemp 2>/dev/null || true)"
    if [ -z "$tmp_file" ]; then
        return 1
    fi
    : > "$tmp_file" || { rm -f "$tmp_file" >/dev/null 2>&1; return 1; }
    local pem_file=""
    for pem_file in "$source_dir"/*.pem; do
        if [ -f "$pem_file" ]; then
            cat "$pem_file" >> "$tmp_file" 2>/dev/null || true
            printf "\n" >> "$tmp_file" 2>/dev/null || true
        fi
    done
    if [ ! -s "$tmp_file" ]; then
        rm -f "$tmp_file" >/dev/null 2>&1 || true
        return 1
    fi
    local output_dir
    output_dir="$(dirname "$output_path")"
    mkdir -p "$output_dir" >/dev/null 2>&1 || {
        rm -f "$tmp_file" >/dev/null 2>&1 || true
        return 1
    }
    mv -f "$tmp_file" "$output_path" >/dev/null 2>&1 || {
        rm -f "$tmp_file" >/dev/null 2>&1 || true
        return 1
    }
    chmod 0644 "$output_path" >/dev/null 2>&1 || true
    return 0
}

soai_managed_runtime__ensure_micromamba() {
    local state_dir="$1"
    local micromamba_version="${2:-2.5.0}"
    local offline_mode="${3:-0}"
    local micromamba_dir="${state_dir}/managed_runtime/micromamba"
    local micromamba_bin="${micromamba_dir}/bin/micromamba"
    if [ -x "$micromamba_bin" ]; then
        printf "%s" "$micromamba_bin"
        return
    fi
    if [ "$offline_mode" = "1" ]; then
        soai_managed_runtime__die "STAY_OFFLINE=true but micromamba is missing. Disable STAY_OFFLINE and run once online." || return 1
    fi
    if ! command -v tar >/dev/null 2>&1; then
        soai_managed_runtime__die "tar is required to bootstrap micromamba." || return 1
    fi
    local platform
    platform="$(soai_managed_runtime__detect_platform)" || return 1
    if ! mkdir -p "$micromamba_dir"; then
        soai_managed_runtime__die "Failed to create micromamba dir: ${micromamba_dir}" || return 1
    fi
    local url="https://micro.mamba.pm/api/micromamba/${platform}/${micromamba_version}"
    local tmp_archive
    tmp_archive="$(mktemp)" || { soai_managed_runtime__die "mktemp failed while bootstrapping micromamba." || return 1; }
    local ca_bundle_path="${state_dir}/managed_runtime/system_ca_bundle.crt"
    if ! soai_managed_runtime__build_system_ca_bundle "$ca_bundle_path"; then
        ca_bundle_path=""
    fi
    if command -v curl >/dev/null 2>&1; then
        if [ -n "$ca_bundle_path" ] && [ -s "$ca_bundle_path" ]; then
            curl -fsSL --cacert "$ca_bundle_path" "$url" -o "$tmp_archive" || {
                rm -f "$tmp_archive" >/dev/null 2>&1
                soai_managed_runtime__die "Failed to download micromamba via curl from: ${url}" || return 1
            }
        else
            curl -fsSL "$url" -o "$tmp_archive" || {
                rm -f "$tmp_archive" >/dev/null 2>&1
                soai_managed_runtime__die "Failed to download micromamba via curl from: ${url}" || return 1
            }
        fi
    elif command -v wget >/dev/null 2>&1; then
        if [ -n "$ca_bundle_path" ] && [ -s "$ca_bundle_path" ]; then
            wget --ca-certificate="$ca_bundle_path" -qO "$tmp_archive" "$url" || {
                rm -f "$tmp_archive" >/dev/null 2>&1
                soai_managed_runtime__die "Failed to download micromamba via wget from: ${url}" || return 1
            }
        else
            wget -qO "$tmp_archive" "$url" || {
                rm -f "$tmp_archive" >/dev/null 2>&1
                soai_managed_runtime__die "Failed to download micromamba via wget from: ${url}" || return 1
            }
        fi
    else
        rm -f "$tmp_archive" >/dev/null 2>&1
        soai_managed_runtime__die "curl or wget is required to bootstrap micromamba." || return 1
    fi
    if ! tar -xjf "$tmp_archive" -C "$micromamba_dir"; then
        rm -f "$tmp_archive" >/dev/null 2>&1
        soai_managed_runtime__die "micromamba extraction failed for: ${tmp_archive}" || return 1
    fi
    rm -f "$tmp_archive" >/dev/null 2>&1
    chmod +x "$micromamba_bin" >/dev/null 2>&1
    if [ ! -x "$micromamba_bin" ]; then
        soai_managed_runtime__die "micromamba bootstrap failed: ${micromamba_bin} missing or not executable." || return 1
    fi
    printf "%s" "$micromamba_bin"
}

soai_managed_runtime__is_conda_env_dir() {
    local env_dir="$1"
    [ -x "${env_dir}/bin/python" ] && [ -d "${env_dir}/conda-meta" ]
}

soai_managed_runtime__ensure_env_uses_system_ca() {
    local env_dir="$1"
    if [ -z "$env_dir" ] || [ ! -d "$env_dir" ]; then
        return 0
    fi
    local ssl_dir="${env_dir}/ssl"
    if ! mkdir -p "$ssl_dir" >/dev/null 2>&1; then
        return 0
    fi
    local ca_bundle_path="${ssl_dir}/soai_system_ca_bundle.crt"
    if ! soai_managed_runtime__build_system_ca_bundle "$ca_bundle_path"; then
        return 0
    fi
    local link_path=""
    for link_path in "${ssl_dir}/cert.pem" "${ssl_dir}/cacert.pem"; do
        rm -f "$link_path" >/dev/null 2>&1 || true
        cp -f "$ca_bundle_path" "$link_path" >/dev/null 2>&1 || true
    done
    if [ -x "${env_dir}/bin/python" ]; then
        local certifi_ca_file=""
        certifi_ca_file="$("${env_dir}/bin/python" -c "import certifi; print(certifi.where())" 2>/dev/null || true)"
        case "$certifi_ca_file" in
            "$env_dir"/*)
                if [ -n "$certifi_ca_file" ] && [ -e "$certifi_ca_file" ] && [ ! -d "$certifi_ca_file" ]; then
                    rm -f "$certifi_ca_file" >/dev/null 2>&1 || true
                    cp -f "$ca_bundle_path" "$certifi_ca_file" >/dev/null 2>&1 || true
                fi
                ;;
            *) ;;
        esac
    fi
}
