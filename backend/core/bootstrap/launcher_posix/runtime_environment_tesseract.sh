#!/usr/bin/env bash
# SoAI - POSIX managed Tesseract runtime provisioning [backend/core/bootstrap/launcher_posix/runtime_environment_tesseract.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_managed_runtime__tesseract_is_valid() {
    local env_dir="$1"
    local tesseract_binary="${env_dir}/bin/tesseract"
    local tesseract_data="${env_dir}/share/tessdata"
    if [ ! -x "$tesseract_binary" ] || [ ! -f "${tesseract_data}/eng.traineddata" ]; then
        return 1
    fi
    local version_output=""
    version_output="$("$tesseract_binary" --version 2>&1)" || return 1
    local first_line="${version_output%%$'\n'*}"
    if [ "$first_line" != "tesseract 5.5.3" ]; then
        return 1
    fi
    TESSDATA_PREFIX="$tesseract_data" "$tesseract_binary" --list-langs 2>/dev/null | grep -Fxq 'eng'
}

soai_managed_runtime__prune_tesseract_languages() {
    local env_dir="$1"
    local tesseract_data="${env_dir}/share/tessdata"
    if [ -z "$env_dir" ] || [ ! -d "$tesseract_data" ] || [ -L "$tesseract_data" ]; then
        soai_managed_runtime__die "Managed Tesseract language directory is invalid: ${tesseract_data}" || return 1
    fi
    local language_file=""
    for language_file in "$tesseract_data"/*.traineddata; do
        if [ ! -e "$language_file" ]; then
            continue
        fi
        if [ "${language_file##*/}" = "eng.traineddata" ]; then
            continue
        fi
        if [ ! -f "$language_file" ] || [ -L "$language_file" ]; then
            soai_managed_runtime__die "Managed Tesseract language entry is invalid: ${language_file}" || return 1
        fi
        rm -f -- "$language_file" || {
            soai_managed_runtime__die "Failed to prune unused managed Tesseract language data: ${language_file}" || return 1
        }
    done
}

soai_managed_runtime__publish_tesseract_environment() {
    local env_dir="$1"
    export SOAI_TESSERACT_CMD="${env_dir}/bin/tesseract"
    export TESSDATA_PREFIX="${env_dir}/share/tessdata"
}

soai_managed_runtime__ensure_tesseract() {
    local env_dir="$1"
    local state_dir="$2"
    local micromamba_version="${3:-2.5.0}"
    local offline_mode="${4:-0}"
    if soai_managed_runtime__tesseract_is_valid "$env_dir"; then
        soai_managed_runtime__prune_tesseract_languages "$env_dir" || return 1
        soai_managed_runtime__publish_tesseract_environment "$env_dir"
        return 0
    fi
    unset SOAI_TESSERACT_CMD TESSDATA_PREFIX
    if [ "$offline_mode" = "1" ]; then
        return 0
    fi
    local micromamba_bin=""
    micromamba_bin="$(soai_managed_runtime__ensure_micromamba "$state_dir" "$micromamba_version" "$offline_mode")" || {
        soai_managed_runtime__warn "Managed Tesseract OCR could not be installed. Raster-only document OCR will report unavailable."
        return 0
    }
    local mamba_root="${state_dir}/managed_runtime/mamba_root"
    if ! mkdir -p "$mamba_root"; then
        soai_managed_runtime__warn "Managed Tesseract OCR storage could not be prepared. Raster-only document OCR will report unavailable."
        return 0
    fi
    if ! soai_install__run_noisy_command "$micromamba_bin" install -y -p "$env_dir" \
            --root-prefix "$mamba_root" \
            --no-rc \
            --override-channels \
            -c conda-forge \
            "tesseract=5.5.3"; then
        soai_managed_runtime__warn "Managed Tesseract OCR installation failed. Raster-only document OCR will report unavailable."
        return 0
    fi
    if ! soai_managed_runtime__tesseract_is_valid "$env_dir"; then
        soai_managed_runtime__warn "Managed Tesseract 5.5.3 English OCR validation failed. Raster-only document OCR will report unavailable."
        return 0
    fi
    soai_managed_runtime__prune_tesseract_languages "$env_dir" || return 1
    soai_managed_runtime__publish_tesseract_environment "$env_dir"
}
