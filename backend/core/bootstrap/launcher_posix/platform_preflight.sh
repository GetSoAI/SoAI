#!/usr/bin/env bash
# SoAI - POSIX launcher platform dependency preflight [backend/core/bootstrap/launcher_posix/platform_preflight.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_launcher__ensure_linux_host_dependencies() {
    if [ "$SOAI_LAUNCHER_FAST_MANAGEMENT" = "1" ]; then
        return 0
    fi
    if [ "$(uname -s 2>/dev/null || true)" != "Linux" ]; then
        return 0
    fi
    if ! command -v apt-get >/dev/null 2>&1; then
        return 0
    fi

    local -a required_packages=()
    if ! command -v tar >/dev/null 2>&1; then
        required_packages+=("tar")
    fi
    if ! command -v bzip2 >/dev/null 2>&1; then
        required_packages+=("bzip2")
    fi
    if [ ! -d "/etc/ssl/certs" ]; then
        required_packages+=("ca-certificates")
    fi
    if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
        required_packages+=("curl")
    fi
    if [ "${#required_packages[@]}" -eq 0 ]; then
        return 0
    fi

    local elevate=()
    if [ "${EUID:-$(id -u)}" -ne 0 ]; then
        if soai_launcher__select_root_elevation env DEBIAN_FRONTEND=noninteractive apt-get update; then
            elevate=(soai_launcher__run_as_root default-environment)
        else
            soai_managed_runtime__die "Missing system dependencies (${required_packages[*]}) and neither sudo nor su can provide root privileges. Re-run as root or install the packages manually." || return 1
        fi
    fi

    soai_launcher__info "Installing required system packages via apt-get: ${required_packages[*]}..."
    if ! soai_install__run_noisy_command "${elevate[@]}" env DEBIAN_FRONTEND=noninteractive apt-get update; then
        soai_managed_runtime__die "apt-get update failed while installing SoAI system dependencies." || return 1
    fi
    if ! soai_install__run_noisy_command "${elevate[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${required_packages[@]}"; then
        soai_managed_runtime__die "apt-get install failed while installing SoAI system dependencies: ${required_packages[*]}." || return 1
    fi
    return 0
}

soai_launcher__detect_pci_vendor_gpus() {
    local vendor_label="$1"
    local vendor_pattern="$2"
    local tool_name="$3"
    local tool_warning="$4"
    if [ "$SOAI_LAUNCHER_FAST_MANAGEMENT" = "1" ] || ! command -v lspci >/dev/null 2>&1; then
        return 0
    fi
    local vendor_gpu_index=0
    local found_gpu=0
    local pci_line=""
    while IFS= read -r pci_line; do
        if ! printf "%s" "$pci_line" | grep -qiE "VGA|Display|3D"; then
            continue
        fi
        if ! printf "%s" "$pci_line" | grep -qiE "$vendor_pattern"; then
            continue
        fi
        local gpu_name=""
        gpu_name="$(printf "%s" "$pci_line" | sed 's/.*: //')"
        if [ -z "$gpu_name" ]; then
            continue
        fi
        soai_launcher__info "${vendor_label} GPU detected (${gpu_name}). GPU index: ${vendor_gpu_index}."
        vendor_gpu_index=$((vendor_gpu_index + 1))
        found_gpu=1
    done < <(lspci 2>/dev/null || true)
    if [ "$found_gpu" = "1" ] && [ -n "$tool_name" ] && ! command -v "$tool_name" >/dev/null 2>&1; then
        soai_launcher__warn "$tool_warning"
    fi
}

soai_launcher__detect_amd_gpu() {
    soai_launcher__detect_pci_vendor_gpus "AMD" "AMD|Advanced Micro Devices|\\[AMD/ATI\\]" "amd-smi" "amd-smi not found. AMD GPU monitoring/control will be unavailable."
}

soai_launcher__detect_intel_gpu() {
    soai_launcher__detect_pci_vendor_gpus "Intel" "Intel" "xpu-smi" "xpu-smi not found. Intel GPU monitoring/control will be unavailable."
}

soai_launcher__run_startup_preflight() {
    if [ "$SOAI_LAUNCHER_FAST_MANAGEMENT" = "1" ]; then
        return 0
    fi
    if [ "$OFFLINE_MODE_ENABLED" = "1" ]; then
        soai_launcher__info "Offline mode detected in configuration (${CONFIG_PATH:-unknown}). Automatic downloads are disabled."
    fi
    soai_launcher__detect_amd_gpu
    soai_launcher__detect_intel_gpu
    soai_launcher__info "Platform checks passed. Handing off to SoAI main application..."
}
