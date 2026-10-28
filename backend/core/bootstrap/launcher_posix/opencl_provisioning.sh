#!/usr/bin/env bash
# SoAI - POSIX launcher OpenCL dependency provisioning [backend/core/bootstrap/launcher_posix/opencl_provisioning.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

SOAI_LAUNCHER_NVIDIA_MODULE_VERSION_PATH="/sys/module/nvidia/version"
SOAI_LAUNCHER_REBOOT_REQUIRED_PATH="/run/reboot-required"
SOAI_LAUNCHER_OPENCL_REPORTED_PACKAGE_LIMIT=8
SOAI_LAUNCHER_OPENCL_DRIVER_COMPONENT_PATTERN='^(linux-|dkms$|firmware-|xserver-xorg-video-|nvidia-(driver|headless|kernel|dkms|firmware|alternative|open))|-(dkms|kernel|modules)(-|$)'
SOAI_LAUNCHER_NVIDIA_PACKAGE_PATTERN='^(lib)?nvidia-'
SOAI_LAUNCHER_NVIDIA_DRIVER_PACKAGE_PATTERN='^nvidia-(driver|headless(-no-dkms)?)(-[0-9]+(-server)?(-open)?)?$'

soai_launcher__apt_candidate_version() {
    local package_name="$1"
    local candidate=""
    candidate="$(apt-cache policy "$package_name" 2>/dev/null | awk '/Candidate:/ {print $2; exit}' || true)"
    if [ "$candidate" != "(none)" ]; then
        printf '%s' "$candidate"
    fi
}

soai_launcher__package_installed() {
    local package_name="$1"
    local native_architecture=""
    native_architecture="$(dpkg --print-architecture 2>/dev/null || true)"
    [ -n "$native_architecture" ] || return 1
    dpkg-query -W -f='${db:Status-Status} ${db:Status-Eflag} ${Architecture}\n' "$package_name" 2>/dev/null \
        | awk -v native="$native_architecture" '$1 == "installed" && $2 == "ok" && ($3 == native || $3 == "all") {found=1} END {exit found ? 0 : 1}'
}

soai_launcher__opencl_package_summary() {
    local -a package_names=("$@")
    local limit="$SOAI_LAUNCHER_OPENCL_REPORTED_PACKAGE_LIMIT"
    if [ "${#package_names[@]}" -le "$limit" ]; then
        printf '%s' "${package_names[*]}"
        return 0
    fi
    printf '%s and %s more' "${package_names[*]:0:$limit}" "$((${#package_names[@]} - limit))"
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
            if (line ~ /advanced micro devices|(^|[^a-z0-9])(amd|ati)([^a-z0-9]|$)/) amd=1
            if (line ~ /intel/) intel=1
        }
        END {
            if (nvidia) print "nvidia"
            if (amd) print "amd"
            if (intel) print "intel"
        }
    '
}

soai_launcher__upstream_package_version() {
    local version="$1"
    case "$version" in *:*) version="${version#*:}" ;; esac
    case "$version" in *-*) version="${version%-*}" ;; esac
    printf '%s' "$version"
}

soai_launcher__installed_nvidia_driver_packages() {
    dpkg-query -W -f='${db:Status-Status} ${db:Status-Eflag} ${Package} ${Version}\n' 'nvidia-driver*' 'nvidia-headless*' 2>/dev/null \
        | awk -v pattern="$SOAI_LAUNCHER_NVIDIA_DRIVER_PACKAGE_PATTERN" '$1 == "installed" && $2 == "ok" && $3 ~ pattern {print $3, $4}' || true
}

soai_launcher__opencl_host_state_blocker() {
    local package_states=""
    local status=0
    package_states="$(dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' 2>/dev/null)" || status=$?
    if [ "$status" -ne 0 ] || [ -z "$package_states" ]; then
        printf '%s' "Installed package state could not be inspected. Repair the distribution package manager, then rerun SoAI install-deps."
        return 0
    fi
    local -a interrupted_packages=()
    mapfile -t interrupted_packages < <(printf '%s\n' "$package_states" | awk 'substr($0, 2, 1) ~ /[HUFWt]/ || substr($0, 3, 1) == "R" {print $NF}')
    if [ "${#interrupted_packages[@]}" -gt 0 ]; then
        printf 'The package manager reports an interrupted or incomplete operation for: %s. Complete the pending distribution package operation (for example: dpkg --configure -a) and repair any reported driver error, then rerun SoAI install-deps.' "$(soai_launcher__opencl_package_summary "${interrupted_packages[@]}")"
        return 0
    fi
    if [ -e "$SOAI_LAUNCHER_REBOOT_REQUIRED_PATH" ]; then
        local reboot_packages_path="${SOAI_LAUNCHER_REBOOT_REQUIRED_PATH}.pkgs"
        local -a relevant_packages=()
        if [ -r "$reboot_packages_path" ]; then
            mapfile -t relevant_packages < <(awk -v driver="$SOAI_LAUNCHER_OPENCL_DRIVER_COMPONENT_PATTERN" -v nvidia="$SOAI_LAUNCHER_NVIDIA_PACKAGE_PATTERN" '$1 ~ driver || $1 ~ nvidia {print $1}' "$reboot_packages_path" | sort -u)
        fi
        if [ ! -r "$reboot_packages_path" ] || [ "${#relevant_packages[@]}" -gt 0 ]; then
            printf 'A system restart is pending%s. Restart the system, then rerun SoAI install-deps.' "${relevant_packages[0]:+ for kernel or graphics-driver packages: $(soai_launcher__opencl_package_summary "${relevant_packages[@]}")}"
            return 0
        fi
    fi
    return 1
}

soai_launcher__append_opencl_candidate() {
    local package_name="$1"
    local -n opencl_candidate_sets_ref="$2"
    local -n opencl_warnings_ref="$3"
    if soai_launcher__package_installed "$package_name"; then
        return 0
    fi
    if [ -n "$(soai_launcher__apt_candidate_version "$package_name")" ]; then
        opencl_candidate_sets_ref+=("$package_name")
    else
        opencl_warnings_ref+=("OpenCL package candidate not available: ${package_name}")
    fi
}

soai_launcher__append_alternative_opencl_candidates() {
    local candidate_sets_array_name="$1"
    local warnings_array_name="$2"
    shift 2
    local -n alternative_candidate_sets_ref="$candidate_sets_array_name"
    local -n alternative_warnings_ref="$warnings_array_name"
    local -a available_packages=()
    local package_name=""
    for package_name in "$@"; do
        if soai_launcher__package_installed "$package_name"; then
            return 0
        fi
    done
    for package_name in "$@"; do
        if [ -n "$(soai_launcher__apt_candidate_version "$package_name")" ]; then
            available_packages+=("$package_name")
        fi
    done
    if [ "${#available_packages[@]}" -eq 0 ]; then
        alternative_warnings_ref+=("No OpenCL ICD package candidate available from this vendor set: $*")
        return 0
    fi
    alternative_candidate_sets_ref+=("${available_packages[*]}")
}

soai_launcher__append_nvidia_opencl_candidate() {
    local candidate_sets_array_name="$1"
    local warnings_array_name="$2"
    local driver_version_name="$3"
    local -n nvidia_candidate_sets_ref="$candidate_sets_array_name"
    local -n nvidia_warnings_ref="$warnings_array_name"
    local -n nvidia_driver_version_ref="$driver_version_name"
    local guidance="Install or repair the distribution NVIDIA driver and its matching OpenCL runtime, then rerun SoAI install-deps. SoAI Bench GPU tests require a working OpenCL runtime."
    local installed_providers=""
    installed_providers="$(dpkg-query -W -f='${db:Status-Status} ${db:Status-Eflag} ${Package} ${Provides}\n' 'libnvidia-compute-*' 'nvidia-driver-*' 'nvidia-headless-*' 'nvidia-opencl-icd' 2>/dev/null || true)"
    if printf '%s\n' "$installed_providers" | awk '$1 == "installed" && $2 == "ok" && ($3 == "nvidia-opencl-icd" || / nvidia-opencl-icd([ ,(]|$)/) {found=1} END {exit found ? 0 : 1}'; then
        return 0
    fi
    local -a driver_packages=()
    mapfile -t driver_packages < <(soai_launcher__installed_nvidia_driver_packages)
    if [ "${#driver_packages[@]}" -eq 0 ]; then
        nvidia_warnings_ref+=("NVIDIA OpenCL is not installed and no installed distribution NVIDIA driver was found. ${guidance}")
        return 0
    fi
    local -a driver_versions=()
    mapfile -t driver_versions < <(printf '%s\n' "${driver_packages[@]}" | awk '{print $2}' | sort -u)
    if [ "${#driver_versions[@]}" -ne 1 ]; then
        nvidia_warnings_ref+=("Installed NVIDIA driver packages have inconsistent versions: $(soai_launcher__opencl_package_summary "${driver_packages[@]}"). ${guidance}")
        return 0
    fi
    local driver_version="${driver_versions[0]}"
    local module_version=""
    if [ -r "$SOAI_LAUNCHER_NVIDIA_MODULE_VERSION_PATH" ]; then
        IFS= read -r module_version < "$SOAI_LAUNCHER_NVIDIA_MODULE_VERSION_PATH" || true
    fi
    if [ -n "$module_version" ] && [ "$module_version" != "$(soai_launcher__upstream_package_version "$driver_version")" ]; then
        nvidia_warnings_ref+=("The loaded NVIDIA kernel module ${module_version} does not match the installed NVIDIA driver ${driver_version}. Restart the system or repair the distribution NVIDIA driver, then rerun SoAI install-deps.")
        return 0
    fi
    local -a runtime_packages=()
    mapfile -t runtime_packages < <(printf '%s\n' "${driver_packages[@]}" | awk '$1 ~ /-[0-9]+/ {name=$1; sub(/^nvidia-(driver|headless(-no-dkms)?)-/, "", name); sub(/-open$/, "", name); print "libnvidia-compute-" name}' | sort -u)
    runtime_packages+=("nvidia-opencl-icd")
    local -a rejected_candidates=()
    local package_name=""
    local candidate_version=""
    for package_name in "${runtime_packages[@]}"; do
        if soai_launcher__package_installed "$package_name"; then
            return 0
        fi
    done
    for package_name in "${runtime_packages[@]}"; do
        candidate_version="$(soai_launcher__apt_candidate_version "$package_name")"
        [ -n "$candidate_version" ] || continue
        if [ "$candidate_version" = "$driver_version" ]; then
            nvidia_candidate_sets_ref+=("$package_name")
            nvidia_driver_version_ref="$driver_version"
            return 0
        fi
        rejected_candidates+=("${package_name} ${candidate_version}")
    done
    if [ "${#rejected_candidates[@]}" -gt 0 ]; then
        nvidia_warnings_ref+=("NVIDIA OpenCL runtime candidates do not match the installed NVIDIA driver ${driver_version}: $(soai_launcher__opencl_package_summary "${rejected_candidates[@]}"). Update the distribution NVIDIA driver through the distribution package manager first, then rerun SoAI install-deps.")
        return 0
    fi
    nvidia_warnings_ref+=("NVIDIA OpenCL is unavailable from the configured repositories for the installed NVIDIA driver ${driver_version}. ${guidance}")
}

soai_launcher__append_vendor_opencl_candidates() {
    local candidate_sets_array_name="$1"
    local warnings_array_name="$2"
    local driver_version_name="$3"
    local vendor=""
    while IFS= read -r vendor; do
        case "$vendor" in
            nvidia)
                soai_launcher__append_nvidia_opencl_candidate "$candidate_sets_array_name" "$warnings_array_name" "$driver_version_name"
                ;;
            amd)
                soai_launcher__append_alternative_opencl_candidates "$candidate_sets_array_name" "$warnings_array_name" "rocm-opencl-icd" "mesa-opencl-icd"
                ;;
            intel)
                soai_launcher__append_alternative_opencl_candidates "$candidate_sets_array_name" "$warnings_array_name" "intel-opencl-icd" "mesa-opencl-icd"
                ;;
            *) ;;
        esac
    done < <(soai_launcher__detect_opencl_gpu_vendors)
}

soai_launcher__warn_opencl_provisioning() {
    local warning=""
    for warning in "$@"; do
        if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then soai_launcher__info "$warning"; fi
        soai_launcher__warn "$warning"
    done
}

soai_launcher__classify_opencl_simulation() {
    local nvidia_driver_version="$1"
    awk -v driver="$SOAI_LAUNCHER_OPENCL_DRIVER_COMPONENT_PATTERN" \
        -v nvidia="$SOAI_LAUNCHER_NVIDIA_PACKAGE_PATTERN" \
        -v nvidia_version="$nvidia_driver_version" '
        /^Inst / {
            if ($3 ~ /^\[/) { print "changed", $2; next }
            if ($3 !~ /^\(/ || !match($0, /\[[^] ]+\]\)/)) { print "unclassified", $2; next }
            architecture = substr($0, RSTART + 1, RLENGTH - 3)
            name = $2
            if (index(name, ":") > 0) {
                if (substr(name, index(name, ":") + 1) != architecture) { print "unclassified", $2; next }
                name = substr(name, 1, index(name, ":") - 1)
            }
            version = substr($3, 2)
            installed[name] = 1
            install_count++
            if (name ~ driver) print "driver", name
            else if (name ~ nvidia && (nvidia_version == "" || version != nvidia_version)) print "nvidia", name
            else print "install", name, architecture, version
            next
        }
        /^(Remv|Purg) / { print "remove", $2; next }
        /^Conf / {
            name = $2
            if (index(name, ":") > 0) name = substr(name, 1, index(name, ":") - 1)
            configured[name] = $2
            next
        }
        /^[A-Z][a-z][a-z][a-z] [^ ]+ [[(]/ { print "unclassified", $2; next }
        /^[0-9]+ upgraded, [0-9]+ newly installed, [0-9]+ to remove and [0-9]+ not upgraded\.$/ {
            summary_count++
            upgraded = $1
            newly_installed = $3
            removed = $6
        }
        END {
            for (name in configured) {
                if (!(name in installed)) print "changed", configured[name]
            }
            if (summary_count != 1 || upgraded != 0 || removed != 0 || newly_installed != install_count || install_count == 0) {
                print "unclassified", "transaction-summary"
            }
        }
    '
}

soai_launcher__admit_opencl_transaction() {
    local -n admission_elevate_ref="$1"
    local nvidia_driver_version="$2"
    local -n admitted_transaction_ref="$3"
    local -n admission_rejection_ref="$4"
    shift 4
    admitted_transaction_ref=()
    admission_rejection_ref=""
    local -a simulation_command=(env LC_ALL=C DEBIAN_FRONTEND=noninteractive apt-get -s install -y --no-remove --no-upgrade --no-install-recommends "$@")
    local output=""
    local status=0
    if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then
        soai_install_ui__capture "Checking OpenCL package transaction" "${admission_elevate_ref[@]}" "${simulation_command[@]}" || status=$?
        output="$(cat "$SOAI_INSTALL_UI_LAST_ATTEMPT/stdout.log" "$SOAI_INSTALL_UI_LAST_ATTEMPT/stderr.log")" || status=1
    else
        output="$("${admission_elevate_ref[@]}" "${simulation_command[@]}" 2>&1)" || status=$?
    fi
    case "$status" in 129|130|143) exit "$status" ;; esac
    if [ "$status" -ne 0 ]; then
        if [ "${SOAI_INSTALL_UI_ENABLED:-0}" != 1 ]; then soai_launcher__info "$output"; fi
        admission_rejection_ref="OpenCL apt simulation failed for: $*. Resolve the package-manager error and rerun SoAI install-deps."
        return 1
    fi
    local classification=""
    classification="$(printf '%s\n' "$output" | soai_launcher__classify_opencl_simulation "$nvidia_driver_version")"
    local -a removed=() changed=() driver_components=() nvidia_components=() unclassified=()
    local operation="" name="" architecture="" version=""
    while read -r operation name architecture version; do
        [ -n "$operation" ] || continue
        case "$operation" in
            install) admitted_transaction_ref+=("${name} ${architecture} ${version}") ;;
            remove) removed+=("$name") ;;
            changed) changed+=("$name") ;;
            driver) driver_components+=("$name") ;;
            nvidia) nvidia_components+=("$name") ;;
            *) unclassified+=("$name") ;;
        esac
    done <<< "$classification"
    if [ "${#removed[@]}" -gt 0 ]; then
        admission_rejection_ref="apt would remove installed packages: $(soai_launcher__opencl_package_summary "${removed[@]}")"
    elif [ "${#changed[@]}" -gt 0 ]; then
        admission_rejection_ref="apt would upgrade, downgrade or reinstall installed packages: $(soai_launcher__opencl_package_summary "${changed[@]}")"
    elif [ "${#driver_components[@]}" -gt 0 ]; then
        admission_rejection_ref="apt would install kernel, DKMS or graphics-driver components: $(soai_launcher__opencl_package_summary "${driver_components[@]}")"
    elif [ "${#nvidia_components[@]}" -gt 0 ]; then
        admission_rejection_ref="apt would install NVIDIA components that do not match the installed NVIDIA driver${nvidia_driver_version:+ ${nvidia_driver_version}}: $(soai_launcher__opencl_package_summary "${nvidia_components[@]}")"
    elif [ "${#unclassified[@]}" -gt 0 ]; then
        admission_rejection_ref="apt reported a transaction that could not be validated"
    fi
    if [ -n "$admission_rejection_ref" ]; then
        admitted_transaction_ref=()
        return 1
    fi
    for name in "$@"; do
        if ! printf '%s\n' "${admitted_transaction_ref[@]}" | awk -v requested="$name" '$1 == requested {found=1} END {exit found ? 0 : 1}'; then
            admission_rejection_ref="apt reported a transaction that could not be validated"
            admitted_transaction_ref=()
            return 1
        fi
    done
}

soai_launcher__select_admitted_opencl_packages() {
    local elevate_array_name="$1"
    local nvidia_driver_version="$2"
    local candidate_sets_array_name="$3"
    local packages_array_name="$4"
    local warnings_array_name="$5"
    local -n selection_candidate_sets_ref="$candidate_sets_array_name"
    local -n selection_packages_ref="$packages_array_name"
    local -n selection_warnings_ref="$warnings_array_name"
    local -a candidate_transaction=()
    local candidate_rejection=""
    local candidate_set=""
    local package_name=""
    for candidate_set in "${selection_candidate_sets_ref[@]}"; do
        local -a candidate_packages=()
        local -a rejected_candidates=()
        read -r -a candidate_packages <<< "$candidate_set"
        for package_name in "${candidate_packages[@]}"; do
            if soai_launcher__admit_opencl_transaction "$elevate_array_name" "$nvidia_driver_version" candidate_transaction candidate_rejection "$package_name"; then
                selection_packages_ref+=("$package_name")
                rejected_candidates=()
                break
            fi
            rejected_candidates+=("Skipping optional SoAI Bench OpenCL package ${package_name}: ${candidate_rejection}")
        done
        if [ "${#rejected_candidates[@]}" -gt 0 ]; then
            selection_warnings_ref+=("${rejected_candidates[@]}")
            if [ "${#candidate_packages[@]}" -gt 1 ]; then
                selection_warnings_ref+=("No safe OpenCL provider is available for: ${candidate_set}. Check the distribution GPU driver and configured repositories, then rerun SoAI install-deps.")
            fi
        fi
    done
}

soai_launcher__prepare_opencl_transaction_guard() {
    local -n prepared_guard_directory_ref="$1"
    prepared_guard_directory_ref=""
    local created_directory=""
    if ! created_directory="$(umask 077; mktemp -d "${TMPDIR:-/tmp}/soai-opencl-transaction.XXXXXXXX")"; then
        soai_launcher__warn_opencl_provisioning "Skipping optional SoAI Bench OpenCL package install: a private directory for the APT transaction guard could not be created. Check free space and permissions of the temporary directory, then rerun SoAI install-deps."
        return 1
    fi
    if ! [[ "$created_directory" =~ ^/[A-Za-z0-9._/+-]+$ ]]; then
        rm -rf -- "$created_directory"
        soai_launcher__warn_opencl_provisioning "Skipping optional SoAI Bench OpenCL package install: the temporary directory path contains spaces or shell metacharacters that the APT transaction guard cannot accept. Set TMPDIR to a plain path, then rerun SoAI install-deps."
        return 1
    fi
    if ! { cp -- "${SOAI_LAUNCHER_MODULE_DIR}/opencl_transaction_guard.sh" "${created_directory}/opencl_transaction_guard.sh" \
        && chmod 0700 "${created_directory}/opencl_transaction_guard.sh"; }; then
        rm -rf -- "$created_directory"
        soai_launcher__warn_opencl_provisioning "Skipping optional SoAI Bench OpenCL package install: the APT transaction guard could not be prepared. Check the SoAI installation files, then rerun SoAI install-deps."
        return 1
    fi
    prepared_guard_directory_ref="$created_directory"
}

soai_launcher__install_admitted_opencl_transaction() {
    local -n install_elevate_ref="$1"
    local guard_directory="$2"
    local -n install_transaction_ref="$3"
    shift 3
    local guard="${guard_directory}/opencl_transaction_guard.sh"
    local admitted="${guard_directory}/admitted-transaction"
    printf '%s\n' "${install_transaction_ref[@]}" > "$admitted" || return 1
    local -a pinned_packages=()
    local package_name="" entry_name="" entry_architecture="" entry_version=""
    for package_name in "$@"; do
        while read -r entry_name entry_architecture entry_version; do
            if [ "$entry_name" = "$package_name" ]; then
                pinned_packages+=("${entry_name}:${entry_architecture}=${entry_version}")
            fi
        done < "$admitted"
    done
    soai_install__run_noisy_command "${install_elevate_ref[@]}" env DEBIAN_FRONTEND=noninteractive apt-get \
        -o Acquire::Retries=2 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 -o DPkg::Lock::Timeout=60 \
        -o "DPkg::Pre-Install-Pkgs::=${guard} ${admitted}" -o "DPkg::Tools::Options::${guard}::Version=3" \
        install -y --no-remove --no-upgrade --no-install-recommends "${pinned_packages[@]}"
}

soai_launcher__provision_soaibench_opencl() {
    if [ "$(uname -s 2>/dev/null || true)" != "Linux" ]; then
        return 0
    fi
    if ! command -v apt-get >/dev/null 2>&1 || ! command -v apt-cache >/dev/null 2>&1; then
        soai_launcher__warn_opencl_provisioning "Skipping optional SoAI Bench OpenCL provisioning: apt-get/apt-cache not available."
        return 0
    fi
    local -a candidate_sets=()
    local -a packages=()
    local -a warnings=()
    local -a elevate=()
    local nvidia_driver_version=""
    if [ "$(id -u)" -ne 0 ]; then
        if ! soai_launcher__select_root_elevation env DEBIAN_FRONTEND=noninteractive apt-get update \
            || [ "$SOAI_LAUNCHER_ROOT_ELEVATION" = "su" ]; then
            soai_launcher__warn_opencl_provisioning "Skipping optional SoAI Bench OpenCL package install: root privileges through sudo are not available."
            return 0
        fi
        elevate=(soai_launcher__run_as_root default-environment)
    fi
    soai_launcher__info "Refreshing package metadata for SoAI Bench OpenCL provisioning."
    local status=0
    soai_install__run_noisy_command "${elevate[@]}" env DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update || status=$?
    case "$status" in 129|130|143) exit "$status" ;; esac
    if [ "$status" -ne 0 ]; then
        soai_launcher__warn_opencl_provisioning "OpenCL package metadata could not be refreshed. Check the configured repositories and network, then rerun SoAI install-deps. SoAI Bench GPU tests remain unavailable without a working OpenCL runtime."
        return 0
    fi
    soai_launcher__append_opencl_candidate "ocl-icd-libopencl1" candidate_sets warnings
    soai_launcher__append_opencl_candidate "clinfo" candidate_sets warnings
    soai_launcher__append_vendor_opencl_candidates candidate_sets warnings nvidia_driver_version
    if [ "${#candidate_sets[@]}" -eq 0 ]; then
        soai_launcher__warn_opencl_provisioning "${warnings[@]}"
        return 0
    fi
    local host_state_blocker=""
    if host_state_blocker="$(soai_launcher__opencl_host_state_blocker)"; then
        soai_launcher__warn_opencl_provisioning "Skipping optional SoAI Bench OpenCL package install: ${host_state_blocker}" "${warnings[@]}"
        return 0
    fi
    soai_launcher__info "Checking optional SoAI Bench OpenCL packages: ${candidate_sets[*]}"
    soai_launcher__select_admitted_opencl_packages elevate "$nvidia_driver_version" candidate_sets packages warnings
    if [ "${#packages[@]}" -eq 0 ]; then
        soai_launcher__warn_opencl_provisioning "${warnings[@]}"
        return 0
    fi
    local -a transaction=()
    local rejection=""
    if ! soai_launcher__admit_opencl_transaction elevate "$nvidia_driver_version" transaction rejection "${packages[@]}"; then
        soai_launcher__warn_opencl_provisioning "Skipping optional SoAI Bench OpenCL package install for ${packages[*]}: ${rejection}" "${warnings[@]}"
        return 0
    fi
    local guard_directory=""
    if ! soai_launcher__prepare_opencl_transaction_guard guard_directory; then
        soai_launcher__warn_opencl_provisioning "${warnings[@]}"
        return 0
    fi
    soai_launcher__install_admitted_opencl_transaction elevate "$guard_directory" transaction "${packages[@]}" || status=$?
    rm -rf -- "$guard_directory"
    case "$status" in 129|130|143) exit "$status" ;; esac
    if [ "$status" -ne 0 ]; then
        soai_launcher__warn_opencl_provisioning "OpenCL package installation failed for: ${packages[*]}. Packages may be partially configured; repair the reported apt/dpkg error and rerun SoAI install-deps, which revalidates the package state before any further change. SoAI Bench GPU tests require a working OpenCL runtime."
        soai_launcher__warn_opencl_provisioning "${warnings[@]}"
        return 0
    fi
    soai_launcher__warn_opencl_provisioning "${warnings[@]}"
}
