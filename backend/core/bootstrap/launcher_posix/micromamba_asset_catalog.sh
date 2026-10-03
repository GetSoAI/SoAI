#!/usr/bin/env bash
# SoAI - POSIX micromamba asset catalog parsing [backend/core/bootstrap/launcher_posix/micromamba_asset_catalog.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_managed_runtime__load_micromamba_asset() {
    local selected_platform_id="$1"
    local requested_version="${2:-}"
    local table_path="${SOAI_LAUNCHER_MODULE_DIR}/micromamba_assets.tsv"
    if [ ! -f "$table_path" ] || [ -L "$table_path" ]; then
        soai_managed_runtime__die "Micromamba asset table is missing or unsafe: ${table_path}" || return 1
    fi
    local row_count=0
    local selected_count=0
    local seen_platforms="|"
    local seen_linux_x64=0
    local seen_linux_arm64=0
    local seen_darwin_x64=0
    local seen_darwin_arm64=0
    local common_version=""
    local line=""
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            *$'\r'*|"")
                soai_managed_runtime__die "Micromamba asset table contains an invalid row." || return 1
                ;;
        esac
        local field_count=""
        field_count="$(awk -F $'\t' '{ print NF }' <<< "$line")" || return 1
        if [ "$field_count" -ne 7 ]; then
            soai_managed_runtime__die "Micromamba asset table row must contain exactly seven fields." || return 1
        fi
        local platform_id=""
        local conda_platform=""
        local version=""
        local build=""
        local url=""
        local archive_name=""
        local sha256=""
        local extra=""
        IFS=$'\t' read -r platform_id conda_platform version build url archive_name sha256 extra <<< "$line"
        if [ -n "$extra" ] || [ -z "$platform_id" ] || [ -z "$conda_platform" ] \
                || [ -z "$version" ] || [ -z "$build" ] || [ -z "$url" ] \
                || [ -z "$archive_name" ] || [ -z "$sha256" ]; then
            soai_managed_runtime__die "Micromamba asset table row has invalid fields." || return 1
        fi
        case "$seen_platforms" in
            *"|${platform_id}|"*)
                soai_managed_runtime__die "Micromamba asset table has a duplicate platform: ${platform_id}" || return 1
                ;;
        esac
        seen_platforms="${seen_platforms}${platform_id}|"
        case "${platform_id}:${conda_platform}" in
            linux-x64:linux-64) seen_linux_x64=$((seen_linux_x64 + 1)) ;;
            linux-arm64:linux-aarch64) seen_linux_arm64=$((seen_linux_arm64 + 1)) ;;
            darwin-x64:osx-64) seen_darwin_x64=$((seen_darwin_x64 + 1)) ;;
            darwin-arm64:osx-arm64) seen_darwin_arm64=$((seen_darwin_arm64 + 1)) ;;
            *) soai_managed_runtime__die "Micromamba asset table has invalid platform coverage." || return 1 ;;
        esac
        if [ "$version" != "2.5.0" ] || [ "$build" != "2" ] \
                || [ "$archive_name" != "micromamba-2.5.0-2.tar.bz2" ] \
                || [ "$url" != "https://api.anaconda.org/download/conda-forge/micromamba/2.5.0/${conda_platform}/micromamba-2.5.0-2.tar.bz2" ]; then
            soai_managed_runtime__die "Micromamba asset table contains an unauthorized pin." || return 1
        fi
        if [[ ! "$sha256" =~ ^[0-9a-f]{64}$ ]]; then
            soai_managed_runtime__die "Micromamba asset table contains an invalid SHA-256." || return 1
        fi
        if [ -z "$common_version" ]; then
            common_version="$version"
        elif [ "$common_version" != "$version" ]; then
            soai_managed_runtime__die "Micromamba asset table versions are inconsistent." || return 1
        fi
        row_count=$((row_count + 1))
        if [ "$platform_id" = "$selected_platform_id" ]; then
            selected_count=$((selected_count + 1))
            SOAI_MICROMAMBA_ASSET_PLATFORM_ID="$platform_id"
            SOAI_MICROMAMBA_ASSET_CONDA_PLATFORM="$conda_platform"
            SOAI_MICROMAMBA_ASSET_VERSION="$version"
            SOAI_MICROMAMBA_ASSET_BUILD="$build"
            SOAI_MICROMAMBA_ASSET_URL="$url"
            SOAI_MICROMAMBA_ASSET_ARCHIVE_NAME="$archive_name"
            SOAI_MICROMAMBA_ASSET_SHA256="$sha256"
        fi
    done < "$table_path"
    if [ "$row_count" -ne 4 ] || [ "$seen_linux_x64" -ne 1 ] || [ "$seen_linux_arm64" -ne 1 ] \
            || [ "$seen_darwin_x64" -ne 1 ] || [ "$seen_darwin_arm64" -ne 1 ]; then
        soai_managed_runtime__die "Micromamba asset table must contain exactly the four release platforms." || return 1
    fi
    if [ "$selected_count" -ne 1 ]; then
        soai_managed_runtime__die "Micromamba asset table lacks the selected platform: ${selected_platform_id}" || return 1
    fi
    if [ -n "$requested_version" ] && [ "$requested_version" != "$SOAI_MICROMAMBA_ASSET_VERSION" ]; then
        soai_managed_runtime__die "Requested micromamba ${requested_version} does not match the release pin ${SOAI_MICROMAMBA_ASSET_VERSION}." || return 1
    fi
}

soai_managed_runtime__default_micromamba_version() {
    local platform_id=""
    platform_id="$(soai_managed_runtime__detect_platform_id)" || return 1
    soai_managed_runtime__load_micromamba_asset "$platform_id" "" || return 1
    printf "%s" "$SOAI_MICROMAMBA_ASSET_VERSION"
}
