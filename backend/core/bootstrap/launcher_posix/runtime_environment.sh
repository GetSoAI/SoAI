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

soai_managed_runtime__detect_platform_id() {
    local conda_platform=""
    conda_platform="$(soai_managed_runtime__detect_platform)" || return 1
    case "$conda_platform" in
        linux-64) printf "linux-x64" ;;
        linux-aarch64) printf "linux-arm64" ;;
        osx-64) printf "darwin-x64" ;;
        osx-arm64) printf "darwin-arm64" ;;
        *) soai_managed_runtime__die "Unsupported micromamba platform: ${conda_platform}" || return 1 ;;
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

soai_managed_runtime__micromamba_binary_matches() {
    local binary_path="$1"
    local expected_version="$2"
    if [ ! -f "$binary_path" ] || [ -L "$binary_path" ] || [ ! -x "$binary_path" ]; then
        return 1
    fi
    local actual_version=""
    actual_version="$("$binary_path" --version 2>/dev/null)" || return 1
    [ "$actual_version" = "$expected_version" ]
}

soai_managed_runtime__read_micromamba_marker() {
    local install_directory="$1"
    local marker_path="${install_directory}/install.tsv"
    if [ ! -f "$marker_path" ] || [ -L "$marker_path" ]; then
        return 1
    fi
    SOAI_MICROMAMBA_MARKER_PLATFORM_ID=""
    SOAI_MICROMAMBA_MARKER_CONDA_PLATFORM=""
    SOAI_MICROMAMBA_MARKER_VERSION=""
    SOAI_MICROMAMBA_MARKER_BUILD=""
    SOAI_MICROMAMBA_MARKER_SELECTED_PIN=""
    SOAI_MICROMAMBA_MARKER_ARCHIVE_SHA256=""
    SOAI_MICROMAMBA_MARKER_PROVENANCE=""
    local line_count=0
    local line=""
    while IFS= read -r line || [ -n "$line" ]; do
        line_count=$((line_count + 1))
        case "$line" in
            platform_id=*) [ -z "$SOAI_MICROMAMBA_MARKER_PLATFORM_ID" ] || return 1; SOAI_MICROMAMBA_MARKER_PLATFORM_ID="${line#platform_id=}" ;;
            conda_platform=*) [ -z "$SOAI_MICROMAMBA_MARKER_CONDA_PLATFORM" ] || return 1; SOAI_MICROMAMBA_MARKER_CONDA_PLATFORM="${line#conda_platform=}" ;;
            version=*) [ -z "$SOAI_MICROMAMBA_MARKER_VERSION" ] || return 1; SOAI_MICROMAMBA_MARKER_VERSION="${line#version=}" ;;
            build=*) [ -z "$SOAI_MICROMAMBA_MARKER_BUILD" ] || return 1; SOAI_MICROMAMBA_MARKER_BUILD="${line#build=}" ;;
            selected_pin=*) [ -z "$SOAI_MICROMAMBA_MARKER_SELECTED_PIN" ] || return 1; SOAI_MICROMAMBA_MARKER_SELECTED_PIN="${line#selected_pin=}" ;;
            archive_sha256=*) [ -z "$SOAI_MICROMAMBA_MARKER_ARCHIVE_SHA256" ] || return 1; SOAI_MICROMAMBA_MARKER_ARCHIVE_SHA256="${line#archive_sha256=}" ;;
            acquisition_provenance=*) [ -z "$SOAI_MICROMAMBA_MARKER_PROVENANCE" ] || return 1; SOAI_MICROMAMBA_MARKER_PROVENANCE="${line#acquisition_provenance=}" ;;
            *) return 1 ;;
        esac
    done < "$marker_path"
    [ "$line_count" -eq 7 ] \
        && [ -n "$SOAI_MICROMAMBA_MARKER_PLATFORM_ID" ] \
        && [ -n "$SOAI_MICROMAMBA_MARKER_CONDA_PLATFORM" ] \
        && [ -n "$SOAI_MICROMAMBA_MARKER_VERSION" ] \
        && [ -n "$SOAI_MICROMAMBA_MARKER_BUILD" ] \
        && [ "$SOAI_MICROMAMBA_MARKER_SELECTED_PIN" = "${SOAI_MICROMAMBA_MARKER_VERSION}-${SOAI_MICROMAMBA_MARKER_BUILD}" ] \
        && [ -n "$SOAI_MICROMAMBA_MARKER_ARCHIVE_SHA256" ] \
        && [ -n "$SOAI_MICROMAMBA_MARKER_PROVENANCE" ]
}

soai_managed_runtime__micromamba_install_is_structurally_valid() {
    local install_directory="$1"
    if [ ! -d "$install_directory" ] || [ -L "$install_directory" ]; then
        return 1
    fi
    soai_managed_runtime__read_micromamba_marker "$install_directory" || return 1
    if [ "$SOAI_MICROMAMBA_MARKER_PLATFORM_ID" != "$SOAI_MICROMAMBA_ASSET_PLATFORM_ID" ] \
            || [ "$SOAI_MICROMAMBA_MARKER_CONDA_PLATFORM" != "$SOAI_MICROMAMBA_ASSET_CONDA_PLATFORM" ]; then
        return 1
    fi
    case "$SOAI_MICROMAMBA_MARKER_PROVENANCE" in
        packaged|network)
            [[ "$SOAI_MICROMAMBA_MARKER_ARCHIVE_SHA256" =~ ^[0-9a-f]{64}$ ]] || return 1
            ;;
        legacy-migrated)
            [ "$SOAI_MICROMAMBA_MARKER_ARCHIVE_SHA256" = "unknown" ] || return 1
            ;;
        *) return 1 ;;
    esac
    soai_managed_runtime__micromamba_binary_matches \
        "${install_directory}/bin/micromamba" \
        "$SOAI_MICROMAMBA_MARKER_VERSION"
}

soai_managed_runtime__micromamba_install_matches() {
    local install_directory="$1"
    soai_managed_runtime__micromamba_install_is_structurally_valid "$install_directory" || return 1
    [ "$SOAI_MICROMAMBA_MARKER_PLATFORM_ID" = "$SOAI_MICROMAMBA_ASSET_PLATFORM_ID" ] \
        && [ "$SOAI_MICROMAMBA_MARKER_CONDA_PLATFORM" = "$SOAI_MICROMAMBA_ASSET_CONDA_PLATFORM" ] \
        && [ "$SOAI_MICROMAMBA_MARKER_VERSION" = "$SOAI_MICROMAMBA_ASSET_VERSION" ] \
        && [ "$SOAI_MICROMAMBA_MARKER_BUILD" = "$SOAI_MICROMAMBA_ASSET_BUILD" ] \
        && { [ "$SOAI_MICROMAMBA_MARKER_ARCHIVE_SHA256" = "$SOAI_MICROMAMBA_ASSET_SHA256" ] \
            || { [ "$SOAI_MICROMAMBA_MARKER_PROVENANCE" = "legacy-migrated" ] \
                && [ "$SOAI_MICROMAMBA_MARKER_ARCHIVE_SHA256" = "unknown" ]; }; }
}

soai_managed_runtime__write_micromamba_marker() {
    local install_directory="$1"
    local provenance="$2"
    local archive_sha256="$3"
    local marker_path="${install_directory}/install.tsv"
    local temporary_marker="${marker_path}.tmp.$$"
    if ! {
        printf "platform_id=%s\n" "$SOAI_MICROMAMBA_ASSET_PLATFORM_ID"
        printf "conda_platform=%s\n" "$SOAI_MICROMAMBA_ASSET_CONDA_PLATFORM"
        printf "version=%s\n" "$SOAI_MICROMAMBA_ASSET_VERSION"
        printf "build=%s\n" "$SOAI_MICROMAMBA_ASSET_BUILD"
        printf "selected_pin=%s-%s\n" "$SOAI_MICROMAMBA_ASSET_VERSION" "$SOAI_MICROMAMBA_ASSET_BUILD"
        printf "archive_sha256=%s\n" "$archive_sha256"
        printf "acquisition_provenance=%s\n" "$provenance"
    } > "$temporary_marker"; then
        rm -f "$temporary_marker" >/dev/null 2>&1 || true
        soai_managed_runtime__die "Failed to write the micromamba installation marker." || return 1
    fi
    mv "$temporary_marker" "$marker_path" || {
        rm -f "$temporary_marker" >/dev/null 2>&1 || true
        soai_managed_runtime__die "Failed to publish the micromamba installation marker." || return 1
    }
}

soai_managed_runtime__select_packaged_micromamba_archive() {
    local output_variable="$1"
    local runtime_assets="${SCRIPT_DIR}/runtime-assets"
    local dependency_directory="${runtime_assets}/micromamba"
    local platform_directory="${dependency_directory}/${SOAI_MICROMAMBA_ASSET_PLATFORM_ID}"
    local archive_path="${platform_directory}/${SOAI_MICROMAMBA_ASSET_ARCHIVE_NAME}"
    local directory_path=""
    for directory_path in "$runtime_assets" "$dependency_directory" "$platform_directory"; do
        if [ -L "$directory_path" ]; then
            soai_managed_runtime__die "Packaged micromamba directory is a symbolic link: ${directory_path}" || return 1
        fi
        if [ ! -e "$directory_path" ]; then
            printf -v "$output_variable" "%s" ""
            return 0
        fi
        if [ ! -d "$directory_path" ]; then
            soai_managed_runtime__die "Packaged micromamba path is not a directory: ${directory_path}" || return 1
        fi
    done
    if [ ! -e "$archive_path" ] && [ ! -L "$archive_path" ]; then
        soai_managed_runtime__die "Packaged micromamba platform directory is incomplete: ${platform_directory}" || return 1
    fi
    if [ ! -f "$archive_path" ] || [ -L "$archive_path" ]; then
        soai_managed_runtime__die "Packaged micromamba archive is unsafe: ${archive_path}" || return 1
    fi
    printf -v "$output_variable" "%s" "$archive_path"
}

soai_managed_runtime__verify_sha256() {
    local path="$1"
    local expected_sha256="$2"
    local actual_sha256=""
    if command -v sha256sum >/dev/null 2>&1; then
        actual_sha256="$(sha256sum "$path" 2>/dev/null | awk '{print $1}')" || return 1
    elif command -v shasum >/dev/null 2>&1; then
        actual_sha256="$(shasum -a 256 "$path" 2>/dev/null | awk '{print $1}')" || return 1
    elif command -v openssl >/dev/null 2>&1; then
        actual_sha256="$(openssl dgst -sha256 "$path" 2>/dev/null | awk '{print $NF}')" || return 1
    else
        soai_managed_runtime__die "A SHA-256 tool is required to verify micromamba." || return 1
    fi
    [ "$actual_sha256" = "$expected_sha256" ]
}

soai_managed_runtime__download_micromamba_archive() {
    local destination="$1"
    local state_dir="$2"
    local maximum_bytes=33554432
    local ca_bundle_path="${state_dir}/managed_runtime/system_ca_bundle.crt"
    if ! soai_managed_runtime__build_system_ca_bundle "$ca_bundle_path"; then
        ca_bundle_path=""
    fi
    if command -v curl >/dev/null 2>&1; then
        local -a curl_arguments=(
            -fsSL --proto '=https' --proto-redir '=https' --max-filesize "$maximum_bytes"
            --connect-timeout 15 --max-time 600 --speed-limit 1024 --speed-time 60
            --retry 3 --retry-delay 2
        )
        if [ -n "$ca_bundle_path" ] && [ -s "$ca_bundle_path" ]; then
            curl_arguments+=(--cacert "$ca_bundle_path")
        fi
        local attempt=1
        local delay=2
        local status=0
        while [ "$attempt" -le 5 ]; do
            rm -f "$destination" || return $?
            status=0
            if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then
                soai_install_ui__capture "Micromamba archive download attempt ${attempt}/5" curl "${curl_arguments[@]}" "$SOAI_MICROMAMBA_ASSET_URL" -o "$destination" || status=$?
            else
                curl "${curl_arguments[@]}" "$SOAI_MICROMAMBA_ASSET_URL" -o "$destination" || status=$?
            fi
            if [ "$status" -eq 0 ]; then break; fi
            if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then
                printf 'Micromamba download attempt %s/5 failed (curl %s).\n' "$attempt" "$status" >> "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log"
            else
                printf 'Micromamba download attempt %s/5 failed (curl %s).\n' "$attempt" "$status" >&2
            fi
            case "$status" in
                5|6|7|18|28|52|55|56|92) ;;
                *) return "$status" ;;
            esac
            if [ "$attempt" -eq 5 ]; then
                return "$status"
            fi
            sleep "$delay" || return $?
            attempt=$((attempt + 1))
            delay=$((delay * 2))
        done
    elif command -v wget >/dev/null 2>&1; then
        local -a wget_arguments=(
            --https-only --quota=32m --timeout=60 --tries=5 --waitretry=16
            --retry-connrefused --retry-on-http-error=408,429,500,502,503,504 -O "$destination"
        )
        if [ -n "$ca_bundle_path" ] && [ -s "$ca_bundle_path" ]; then
            wget_arguments+=(--ca-certificate="$ca_bundle_path")
        fi
        local status=0
        if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then
            soai_install_ui__capture "Micromamba archive download" wget "${wget_arguments[@]}" "$SOAI_MICROMAMBA_ASSET_URL" || status=$?
        else
            wget "${wget_arguments[@]}" "$SOAI_MICROMAMBA_ASSET_URL" || status=$?
        fi
        if [ "$status" -ne 0 ]; then
            soai_managed_runtime__die "Failed to download the pinned micromamba archive via HTTPS." || return 1
        fi
    else
        soai_managed_runtime__die "curl or wget is required to bootstrap micromamba." || return 1
    fi
    local downloaded_bytes=""
    downloaded_bytes="$(wc -c < "$destination" 2>/dev/null)" || return 1
    if [ "$downloaded_bytes" -gt "$maximum_bytes" ]; then
        soai_managed_runtime__die "Downloaded micromamba archive exceeds the 32 MiB limit." || return 1
    fi
}

soai_managed_runtime__publish_micromamba_directory() {
    local staging_directory="$1"
    local install_directory="$2"
    local backup_directory="$3"
    if ! soai_managed_runtime__micromamba_install_matches "$staging_directory"; then
        soai_managed_runtime__die "Micromamba staging directory failed validation." || return 1
    fi
    if [ -e "$backup_directory" ] || [ -L "$backup_directory" ]; then
        if soai_managed_runtime__micromamba_install_matches "$install_directory"; then
            rm -rf "$backup_directory" || return 1
        elif [ ! -e "$install_directory" ] && [ ! -L "$install_directory" ] \
                && soai_managed_runtime__micromamba_install_is_structurally_valid "$backup_directory"; then
            mv "$backup_directory" "$install_directory" || return 1
        else
            soai_managed_runtime__die "Micromamba publication has unrecovered retained state." || return 1
        fi
    fi
    local moved_existing=0
    if [ -e "$install_directory" ] || [ -L "$install_directory" ]; then
        if [ ! -d "$install_directory" ] || [ -L "$install_directory" ]; then
            soai_managed_runtime__die "Existing micromamba installation path is unsafe." || return 1
        fi
        mv "$install_directory" "$backup_directory" || return 1
        moved_existing=1
    fi
    if ! mv "$staging_directory" "$install_directory"; then
        if [ "$moved_existing" = "1" ] && [ ! -e "$install_directory" ]; then
            mv "$backup_directory" "$install_directory" || {
                soai_managed_runtime__die "Micromamba promotion failed and its backup was retained." || return 1
            }
        fi
        soai_managed_runtime__die "Micromamba staging promotion failed." || return 1
    fi
    if ! soai_managed_runtime__micromamba_install_matches "$install_directory"; then
        local failed_directory="${install_directory}.soai-failed.$$"
        mv "$install_directory" "$failed_directory" || {
            soai_managed_runtime__die "Invalid promoted micromamba runtime could not be retained." || return 1
        }
        if [ "$moved_existing" = "1" ]; then
            mv "$backup_directory" "$install_directory" || {
                soai_managed_runtime__die "Micromamba validation failed and its backup was retained." || return 1
            }
        fi
        rm -rf "$failed_directory" >/dev/null 2>&1 || true
        soai_managed_runtime__die "Promoted micromamba runtime failed validation." || return 1
    fi
    if [ "$moved_existing" = "1" ]; then
        rm -rf "$backup_directory" || {
            soai_managed_runtime__die "Completed micromamba backup could not be removed." || return 1
        }
    fi
}

soai_managed_runtime__recover_micromamba_publication() {
    local install_directory="$1"
    local backup_directory="$2"
    if [ ! -e "$backup_directory" ] && [ ! -L "$backup_directory" ]; then
        return 0
    fi
    if [ ! -d "$backup_directory" ] || [ -L "$backup_directory" ]; then
        soai_managed_runtime__die "Retained micromamba backup is unsafe: ${backup_directory}" || return 1
    fi
    if soai_managed_runtime__micromamba_install_matches "$install_directory"; then
        rm -rf "$backup_directory" || {
            soai_managed_runtime__die "Completed micromamba backup could not be removed." || return 1
        }
        return 0
    fi
    if ! soai_managed_runtime__micromamba_install_is_structurally_valid "$backup_directory"; then
        soai_managed_runtime__die "Retained micromamba backup failed validation." || return 1
    fi
    if [ ! -e "$install_directory" ] && [ ! -L "$install_directory" ]; then
        mv "$backup_directory" "$install_directory" || {
            soai_managed_runtime__die "Interrupted micromamba backup restoration failed." || return 1
        }
        return 0
    fi
    if [ ! -d "$install_directory" ] || [ -L "$install_directory" ]; then
        soai_managed_runtime__die "Interrupted micromamba installation path is unsafe." || return 1
    fi
    local failed_directory="${install_directory}.soai-recovery-failed.$$"
    mv "$install_directory" "$failed_directory" || return 1
    if ! mv "$backup_directory" "$install_directory"; then
        mv "$failed_directory" "$install_directory" >/dev/null 2>&1 || true
        soai_managed_runtime__die "Interrupted micromamba backup restoration failed." || return 1
    fi
    rm -rf "$failed_directory" || {
        soai_managed_runtime__die "Recovered micromamba residue could not be removed." || return 1
    }
}

soai_managed_runtime__ensure_micromamba() {
    local state_dir="$1"
    local micromamba_version="${2:-}"
    local offline_mode="${3:-0}"
    if [ -z "$micromamba_version" ]; then
        soai_managed_runtime__die "The micromamba release version must be selected from the asset table." || return 1
    fi
    local platform_id=""
    platform_id="$(soai_managed_runtime__detect_platform_id)" || return 1
    soai_managed_runtime__load_micromamba_asset "$platform_id" "$micromamba_version" || return 1
    local micromamba_dir="${state_dir}/managed_runtime/micromamba"
    local micromamba_bin="${micromamba_dir}/bin/micromamba"
    local marker_path="${micromamba_dir}/install.tsv"
    local backup_directory="${micromamba_dir}.soai-backup"
    soai_managed_runtime__recover_micromamba_publication "$micromamba_dir" "$backup_directory" || return 1
    if soai_managed_runtime__micromamba_install_matches "$micromamba_dir"; then
        printf "%s" "$micromamba_bin"
        return
    fi
    if [ ! -e "$marker_path" ] && [ ! -L "$marker_path" ] \
            && [ -d "$micromamba_dir" ] && [ ! -L "$micromamba_dir" ] \
            && soai_managed_runtime__micromamba_binary_matches "$micromamba_bin" "$SOAI_MICROMAMBA_ASSET_VERSION"; then
        soai_managed_runtime__write_micromamba_marker "$micromamba_dir" "legacy-migrated" "unknown" || return 1
        printf "%s" "$micromamba_bin"
        return
    fi
    if ! command -v tar >/dev/null 2>&1; then
        soai_managed_runtime__die "tar is required to bootstrap micromamba." || return 1
    fi
    local packaged_archive=""
    soai_managed_runtime__select_packaged_micromamba_archive packaged_archive || return 1
    if [ -z "$packaged_archive" ] && [ "$offline_mode" = "1" ]; then
        soai_managed_runtime__die "STAY_OFFLINE=true and the packaged micromamba asset for ${platform_id} is absent." || return 1
    fi
    local managed_runtime_directory="${state_dir}/managed_runtime"
    mkdir -p "$managed_runtime_directory" || {
        soai_managed_runtime__die "Failed to create managed runtime directory: ${managed_runtime_directory}" || return 1
    }
    local archive_path="$packaged_archive"
    local downloaded_archive=""
    local provenance="packaged"
    if [ -z "$archive_path" ]; then
        downloaded_archive="$(mktemp "${managed_runtime_directory}/.micromamba-download.XXXXXX")" || {
            soai_managed_runtime__die "Failed to create a micromamba download file." || return 1
        }
        archive_path="$downloaded_archive"
        provenance="network"
        soai_managed_runtime__download_micromamba_archive "$archive_path" "$state_dir" || {
            rm -f "$downloaded_archive" >/dev/null 2>&1 || true
            return 1
        }
    fi
    if ! soai_managed_runtime__verify_sha256 "$archive_path" "$SOAI_MICROMAMBA_ASSET_SHA256"; then
        rm -f "$downloaded_archive" >/dev/null 2>&1 || true
        soai_managed_runtime__die "Micromamba archive failed its selected SHA-256 pin." || return 1
    fi
    local staging_directory=""
    staging_directory="$(mktemp -d "${managed_runtime_directory}/.micromamba-staging.XXXXXX")" || {
        rm -f "$downloaded_archive" >/dev/null 2>&1 || true
        soai_managed_runtime__die "Failed to create micromamba staging directory." || return 1
    }
    if ! tar -xjf "$archive_path" -C "$staging_directory" bin/micromamba; then
        rm -rf "$staging_directory" >/dev/null 2>&1 || true
        rm -f "$downloaded_archive" >/dev/null 2>&1 || true
        soai_managed_runtime__die "Micromamba extraction failed for the selected archive." || return 1
    fi
    rm -f "$downloaded_archive" >/dev/null 2>&1 || true
    chmod +x "${staging_directory}/bin/micromamba" >/dev/null 2>&1 || true
    if ! soai_managed_runtime__micromamba_binary_matches "${staging_directory}/bin/micromamba" "$SOAI_MICROMAMBA_ASSET_VERSION"; then
        rm -rf "$staging_directory" >/dev/null 2>&1 || true
        soai_managed_runtime__die "Extracted micromamba executable failed exact version validation." || return 1
    fi
    soai_managed_runtime__write_micromamba_marker "$staging_directory" "$provenance" "$SOAI_MICROMAMBA_ASSET_SHA256" || {
        rm -rf "$staging_directory" >/dev/null 2>&1 || true
        return 1
    }
    soai_managed_runtime__publish_micromamba_directory "$staging_directory" "$micromamba_dir" "$backup_directory" || {
        rm -rf "$staging_directory" >/dev/null 2>&1 || true
        return 1
    }
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
