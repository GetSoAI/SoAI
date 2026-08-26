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
        if command -v sudo >/dev/null 2>&1; then
            elevate=("sudo")
        else
            soai_managed_runtime__die "Missing system dependencies (${required_packages[*]}) and sudo is not available. Re-run as root or install the packages manually." || return 1
        fi
    fi

    soai_launcher__info "Installing required system packages via apt-get: ${required_packages[*]}..."
    if ! "${elevate[@]}" env DEBIAN_FRONTEND=noninteractive apt-get update; then
        soai_managed_runtime__die "apt-get update failed while installing SoAI system dependencies." || return 1
    fi
    if ! "${elevate[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${required_packages[@]}"; then
        soai_managed_runtime__die "apt-get install failed while installing SoAI system dependencies: ${required_packages[*]}." || return 1
    fi
    return 0
}

soai_launcher__python_supports_pynvml() {
    local python_bin="$1"
    if [ -z "$python_bin" ] || [ ! -x "$python_bin" ]; then
        return 1
    fi
    "$python_bin" -c "import pynvml" >/dev/null 2>&1
}

soai_launcher__nvidia_settings_control_ready() {
    if [ "$(uname -s 2>/dev/null || true)" != "Linux" ]; then
        printf "0\nnvidia-settings is only used on Linux NVIDIA GPUs"
        return
    fi
    if ! command -v nvidia-settings >/dev/null 2>&1; then
        printf "0\nnvidia-settings not found in PATH"
        return
    fi
    if [ -n "${DISPLAY:-}" ]; then
        printf "1\nDISPLAY is set for nvidia-settings"
        return
    fi
    if pgrep -a Xorg >/dev/null 2>&1; then
        printf "1\nExisting Xorg display detected for nvidia-settings"
        return
    fi
    if ! command -v Xorg >/dev/null 2>&1; then
        printf "0\nXorg not found for headless nvidia-settings"
        return
    fi
    if [ ! -f "/etc/X11/xorg.conf" ]; then
        printf "0\nxorg.conf not found for headless nvidia-settings"
        return
    fi
    printf "1\nHeadless Xorg startup available for nvidia-settings"
}

soai_launcher__resolve_nvidia_control_path() {
    local python_bin="$1"
    local control_method="none"
    local control_reason="No supported NVIDIA control backend available"
    local nvidia_settings_info=""
    nvidia_settings_info="$(soai_launcher__nvidia_settings_control_ready)"
    local nvidia_settings_ready=""
    nvidia_settings_ready="$(printf "%s" "$nvidia_settings_info" | sed -n '1p')"
    local nvidia_settings_reason=""
    nvidia_settings_reason="$(printf "%s" "$nvidia_settings_info" | sed -n '2p')"
    if [ "$nvidia_settings_ready" = "1" ]; then
        control_method="nvidia-settings"
        control_reason="$nvidia_settings_reason"
    elif soai_launcher__python_supports_pynvml "$python_bin"; then
        control_method="pynvml"
        control_reason="NVML available"
    elif [ -n "$python_bin" ] && [ ! -x "$python_bin" ]; then
        control_method="pynvml"
        control_reason="Managed runtime will provide NVML support after environment setup"
    fi
    printf "%s\n%s" "$control_method" "$control_reason"
}

soai_launcher__classify_nvidia_gpu() {
    local gpu_name="$1"
    local ecc_mode="$2"
    local gpu_class="unknown"
    local reason="No matching pattern found"
    if [ "$ecc_mode" = "enabled" ] || [ "$ecc_mode" = "disabled" ]; then
        gpu_class="professional"
        reason="ECC memory support detected"
    elif printf "%s" "$gpu_name" | grep -qiE "\\bTesla\\b|\\bQuadro\\b|\\bGrid\\b|\\bNVS\\s+[0-9]{2,4}\\b|\\bRTX\\s+A[0-9]{4}|\\bRTX\\s+[0-9]{4}\\b.*\\bAda\\b|\\bRTX\\s+Pro\\s+[0-9]{4}|\\bA[0-9]{1,3}\\b|\\bH[0-9]{2,3}\\b|\\bB[0-9]{2,3}\\b|\\bGB[0-9]{2,3}\\b|\\bL[0-9]{1,2}S?\\b|\\bT[0-9]{1,2}\\b|\\bV[0-9]{2,3}\\b"; then
        gpu_class="professional"
        reason="Name matches professional pattern"
    elif printf "%s" "$gpu_name" | grep -qiE "\\bGeForce\\b|\\bGT\\s+[0-9]{3,4}\\b|\\bGTX\\s+[0-9]{3,4}\\b|\\bMX\\s*[0-9]{2,4}\\b|\\bRTX\\s+(20|30|40|50|60|70)[0-9]{2}\\b|\\bTitan\\s+(X|Xp|RTX|V)\\b|\\bGTX\\s+Titan\\b|\\bCMP\\s+[0-9]+HX\\b|\\bP106[-\\s]?100\\b|\\bM40\\b"; then
        gpu_class="consumer"
        reason="Name matches consumer pattern"
    fi
    printf "%s\n%s" "$gpu_class" "$reason"
}

soai_launcher__detect_nvidia_gpu() {
    local python_bin="$1"
    if [ "$SOAI_LAUNCHER_FAST_MANAGEMENT" = "1" ] || ! command -v nvidia-smi >/dev/null 2>&1; then
        return 0
    fi
    local -a gpu_names=()
    local -a ecc_modes=()
    mapfile -t gpu_names < <(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || true)
    if [ "${#gpu_names[@]}" -eq 0 ]; then
        return 0
    fi
    mapfile -t ecc_modes < <(nvidia-smi --query-gpu=ecc.mode.current --format=csv,noheader 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)
    local gpu_index=0
    local gpu_name=""
    for gpu_name in "${gpu_names[@]}"; do
        gpu_name="$(printf "%s" "$gpu_name" | tr -d '\r')"
        if [ -z "$gpu_name" ]; then
            gpu_index=$((gpu_index + 1))
            continue
        fi
        local ecc_mode=""
        if [ "$gpu_index" -lt "${#ecc_modes[@]}" ]; then
            ecc_mode="$(printf "%s" "${ecc_modes[$gpu_index]}" | tr -d '\r')"
        fi
        local classification_info=""
        classification_info="$(soai_launcher__classify_nvidia_gpu "$gpu_name" "$ecc_mode")"
        local gpu_class=""
        gpu_class="$(printf "%s" "$classification_info" | sed -n '1p')"
        local reason=""
        reason="$(printf "%s" "$classification_info" | sed -n '2p')"
        local control_info=""
        control_info="$(soai_launcher__resolve_nvidia_control_path "$python_bin")"
        local control_method=""
        control_method="$(printf "%s" "$control_info" | sed -n '1p')"
        local control_reason=""
        control_reason="$(printf "%s" "$control_info" | sed -n '2p')"
        soai_launcher__info "NVIDIA GPU detected (${gpu_name}). GPU index: ${gpu_index}. Class: ${gpu_class}. Reason: ${reason}. Control path: ${control_method}. Control reason: ${control_reason}."
        gpu_index=$((gpu_index + 1))
    done
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
    local python_bin="$1"
    if [ "$SOAI_LAUNCHER_FAST_MANAGEMENT" = "1" ]; then
        return 0
    fi
    if [ "$OFFLINE_MODE_ENABLED" = "1" ]; then
        soai_launcher__info "Offline mode detected in configuration (${CONFIG_PATH:-unknown}). Automatic downloads are disabled."
    fi
    soai_launcher__detect_nvidia_gpu "$python_bin"
    soai_launcher__detect_amd_gpu
    soai_launcher__detect_intel_gpu
    soai_launcher__info "Platform checks passed. Handing off to SoAI main application..."
}
