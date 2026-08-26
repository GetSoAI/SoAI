#!/usr/bin/env bash
# SoAI - POSIX launcher OpenCL dependency provisioning [backend/core/bootstrap/launcher_posix/opencl_provisioning.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_launcher__apt_candidate_exists() {
    local package_name="$1"
    local candidate=""
    candidate="$(apt-cache policy "$package_name" 2>/dev/null | awk '/Candidate:/ {print $2; exit}' || true)"
    [ -n "$candidate" ] && [ "$candidate" != "(none)" ]
}

soai_launcher__package_installed() {
    local package_name="$1"
    local status=""
    status="$(dpkg-query -W -f='${db:Status-Status}' "$package_name" 2>/dev/null || true)"
    [ "$status" = "installed" ]
}

soai_launcher__detect_opencl_gpu_vendors() {
    if ! command -v lspci >/dev/null 2>&1; then
        return 0
    fi
    lspci 2>/dev/null | awk '
        BEGIN { nvidia=0; amd=0; intel=0 }
        /VGA compatible controller|3D controller|Display controller/ {
            line=tolower($0)
            if (line ~ /nvidia/) nvidia=1
            if (line ~ /advanced micro devices|amd|ati/) amd=1
            if (line ~ /intel/) intel=1
        }
        END {
            if (nvidia) print "nvidia"
            if (amd) print "amd"
            if (intel) print "intel"
        }
    '
}

soai_launcher__append_opencl_candidate() {
    local package_name="$1"
    local -n opencl_packages_ref="$2"
    local -n opencl_warnings_ref="$3"
    if soai_launcher__apt_candidate_exists "$package_name"; then
        opencl_packages_ref+=("$package_name")
    else
        opencl_warnings_ref+=("OpenCL package candidate not available: ${package_name}")
    fi
}

soai_launcher__append_first_opencl_candidate() {
    local packages_array_name="$1"
    local warnings_array_name="$2"
    shift 2
    local -n opencl_packages_ref="$packages_array_name"
    local -n opencl_warnings_ref="$warnings_array_name"
    local package_name=""
    for package_name in "$@"; do
        if soai_launcher__package_installed "$package_name"; then
            opencl_packages_ref+=("$package_name")
            return 0
        fi
    done
    for package_name in "$@"; do
        if soai_launcher__apt_candidate_exists "$package_name"; then
            opencl_packages_ref+=("$package_name")
            return 0
        fi
    done
    opencl_warnings_ref+=("No OpenCL ICD package candidate available from this vendor set: $*")
}

soai_launcher__append_safe_first_opencl_candidate() {
    local packages_array_name="$1"
    local warnings_array_name="$2"
    local elevate_array_name="$3"
    shift 3
    local -n opencl_packages_ref="$packages_array_name"
    local -n opencl_warnings_ref="$warnings_array_name"
    local package_name=""
    for package_name in "$@"; do
        if soai_launcher__package_installed "$package_name"; then
            opencl_packages_ref+=("$package_name")
            return 0
        fi
    done
    for package_name in "$@"; do
        if ! soai_launcher__apt_candidate_exists "$package_name"; then
            opencl_warnings_ref+=("OpenCL package candidate not available: ${package_name}")
            continue
        fi
        if soai_launcher__apt_install_would_remove_packages "$elevate_array_name" "$package_name"; then
            opencl_warnings_ref+=("Skipping OpenCL ICD package because apt would remove installed packages: ${package_name}")
            continue
        fi
        opencl_packages_ref+=("$package_name")
        return 0
    done
}

soai_launcher__append_vendor_opencl_candidates() {
    local packages_array_name="$1"
    local warnings_array_name="$2"
    local elevate_array_name="${3:-}"
    local vendor=""
    while IFS= read -r vendor; do
        case "$vendor" in
            nvidia)
                soai_launcher__append_opencl_candidate "nvidia-opencl-icd" "$packages_array_name" "$warnings_array_name"
                ;;
            amd)
                if [ -n "$elevate_array_name" ]; then
                    soai_launcher__append_safe_first_opencl_candidate "$packages_array_name" "$warnings_array_name" "$elevate_array_name" "rocm-opencl-icd" "mesa-opencl-icd"
                else
                    soai_launcher__append_first_opencl_candidate "$packages_array_name" "$warnings_array_name" "rocm-opencl-icd" "mesa-opencl-icd"
                fi
                ;;
            intel)
                soai_launcher__append_opencl_candidate "intel-opencl-icd" "$packages_array_name" "$warnings_array_name"
                ;;
            *) ;;
        esac
    done < <(soai_launcher__detect_opencl_gpu_vendors)
}

soai_launcher__warn_opencl_provisioning() {
    local warning=""
    for warning in "$@"; do
        soai_launcher__warn "$warning"
    done
}

soai_launcher__apt_install_would_remove_packages() {
    local -n elevate_ref="$1"
    shift
    local output=""
    if ! output="$("${elevate_ref[@]}" env DEBIAN_FRONTEND=noninteractive apt-get -s install -y --no-install-recommends "$@" 2>&1)"; then
        soai_launcher__warn "Optional SoAIBench OpenCL apt simulation failed for: $*"
        return 0
    fi
    printf '%s\n' "$output" | awk '
        /^Remv / { found=1 }
        /The following packages will be REMOVED:/ { found=1 }
        END { exit found ? 0 : 1 }
    '
}

soai_launcher__filter_opencl_packages_without_removals() {
    local elevate_array_name="$1"
    local package_array_name="$2"
    local warning_array_name="$3"
    local -n packages_ref="$package_array_name"
    local -n warnings_ref="$warning_array_name"
    local -a safe_packages=()
    local package_name=""
    for package_name in "${packages_ref[@]}"; do
        if soai_launcher__apt_install_would_remove_packages "$elevate_array_name" "$package_name"; then
            warnings_ref+=("Skipping optional SoAIBench OpenCL package because apt would remove installed packages: ${package_name}")
        else
            safe_packages+=("$package_name")
        fi
    done
    packages_ref=("${safe_packages[@]}")
    if [ "${#packages_ref[@]}" -gt 0 ] && soai_launcher__apt_install_would_remove_packages "$elevate_array_name" "${packages_ref[@]}"; then
        warnings_ref+=("Skipping optional SoAIBench OpenCL package install because the combined apt transaction would remove installed packages: ${packages_ref[*]}")
        packages_ref=()
    fi
}

soai_launcher__provision_soaibench_opencl() {
    if [ "$(uname -s 2>/dev/null || true)" != "Linux" ]; then
        return 0
    fi
    if ! command -v apt-get >/dev/null 2>&1 || ! command -v apt-cache >/dev/null 2>&1; then
        soai_launcher__warn "Skipping optional SoAIBench OpenCL provisioning: apt-get/apt-cache not available."
        return 0
    fi
    local -a packages=()
    local -a warnings=()
    soai_launcher__append_opencl_candidate "ocl-icd-libopencl1" packages warnings
    soai_launcher__append_opencl_candidate "clinfo" packages warnings
    local -a elevate=()
    if [ "$(id -u)" -ne 0 ]; then
        if ! command -v sudo >/dev/null 2>&1; then
            soai_launcher__warn "Skipping optional SoAIBench OpenCL package install: sudo is not available."
            soai_launcher__warn_opencl_provisioning "${warnings[@]}"
            return 0
        fi
        elevate=(sudo)
    fi
    soai_launcher__info "Refreshing package metadata for SoAIBench OpenCL provisioning."
    if ! "${elevate[@]}" env DEBIAN_FRONTEND=noninteractive apt-get update; then
        soai_launcher__warn "Optional SoAIBench OpenCL apt-get update failed; runtime will report unsupported details if OpenCL is unavailable."
        soai_launcher__warn_opencl_provisioning "${warnings[@]}"
        return 0
    fi
    soai_launcher__append_vendor_opencl_candidates packages warnings elevate
    if [ "${#packages[@]}" -eq 0 ]; then
        soai_launcher__warn_opencl_provisioning "${warnings[@]}"
        return 0
    fi
    soai_launcher__info "Checking optional SoAIBench OpenCL packages: ${packages[*]}"
    soai_launcher__filter_opencl_packages_without_removals elevate packages warnings
    if [ "${#packages[@]}" -eq 0 ]; then
        soai_launcher__warn_opencl_provisioning "${warnings[@]}"
        return 0
    fi
    if ! "${elevate[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${packages[@]}"; then
        soai_launcher__warn "Optional SoAIBench OpenCL package install failed; runtime will report unsupported details if OpenCL is unavailable."
        soai_launcher__warn_opencl_provisioning "${warnings[@]}"
        return 0
    fi
    soai_launcher__warn_opencl_provisioning "${warnings[@]}"
}
