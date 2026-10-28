#!/usr/bin/env bash
# SoAI - POSIX launcher installation payload selection [backend/core/bootstrap/launcher_posix/install_payload.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_install__managed_root_entries() {
    printf "%s\n" CHANGE-DATES.md COMMERCIAL-LICENSE.md COMMERCIAL-LICENSING-AVAILABILITY.md COMMERCIAL-SUPPORT-TERMS.md ORGANIZATION-EVALUATION-TERMS.md install-soai-from-release.bat install-soai-from-release.command install-soai-from-release.sh install-soai-linux.sh install-soai-macos.command install-soai-windows.ps1 uninstall-soai-linux.sh
    printf "%s\n" \
        backend \
        frontend \
        plugins \
        licenses \
        docs \
        VERSION \
        release-info-v1.json \
        CHANGE_DATES.md \
        COMMERCIAL_LICENSING_AVAILABILITY.md \
        COMMERCIAL_LICENSE.md \
        COMMERCIAL_SUPPORT_TERMS.md \
        LICENSE.md \
        README.md \
        NOTICE \
        LICENSING.md \
        PRIVACY.md \
        ORGANIZATION_EVALUATION_TERMS.md \
        DOCUMENTATION.md \
        SECURITY.md \
        RELEASE_NOTES.md \
        requirements.txt \
        install_soai_macos.command \
        install_soai_windows.ps1 \
        install_soai_linux.sh \
        soai.sh \
        soai.command \
        soai.exe \
        soai.exe.config \
        soai-app.ico \
        Microsoft.Web.WebView2.Core.dll \
        Microsoft.Web.WebView2.WinForms.dll \
        WebView2Loader.dll \
        msvcp140.dll \
        msvcp140_1.dll \
        msvcp140_2.dll \
        msvcp140_atomic_wait.dll \
        msvcp140_codecvt_ids.dll \
        vcruntime140.dll \
        vcruntime140_1.dll \
        python \
        runtime-assets \
        installer-support \
        install_soai_from_release.sh \
        install_soai_from_release.command \
        install_soai_from_release.bat \
        uninstall_soai_linux.sh
    if [ -n "$SOAI_EXPLICIT_EDITION_ROOT_ENTRIES" ]; then
        printf "%s\n" "$SOAI_EXPLICIT_EDITION_ROOT_ENTRIES"
    fi
}

soai_install__remove_path() {
    local target="$1"
    local path="$2"
    case "$path" in
        "$target"/*) ;;
        *)
            soai_managed_runtime__die "Refusing to remove path outside install target: ${path}" || return 1
            ;;
    esac
    soai_install__run_noisy_command rm -rf -- "$path" || return 1
}

soai_install__copy_existing_entry() {
    local source_entry="$1"
    local target_parent="$2"
    if [ ! -e "$source_entry" ]; then
        return 0
    fi
    if ! soai_install__run_noisy_command mkdir -p "$target_parent"; then
        soai_managed_runtime__die "Failed to create install staging directory: ${target_parent}" || return 1
    fi
    if ! soai_install__run_noisy_command cp -pPR "$source_entry" "$target_parent/"; then
        soai_managed_runtime__die "Failed to copy install payload entry: ${source_entry}" || return 1
    fi
}

soai_install__copy_staging_payload() {
    local source="$1"
    local staging="$2"
    local entry=""
    while IFS= read -r entry; do
        soai_install__copy_existing_entry "${source}/${entry}" "$staging" || return 1
    done < <(soai_install__managed_root_entries)
    soai_install__copy_existing_entry "${source}/data/vendor" "${staging}/data" || return 1
    if [ "${EUID:-$(id -u)}" -eq 0 ] && ! soai_install__run_noisy_command chown -R -h 0:0 "$staging"; then
        soai_managed_runtime__die "Failed to assign root ownership to the install payload: ${staging}" || return 1
    fi
}

soai_install__replace_managed_entries() {
    local target="$1"
    local staging="$2"
    local backup="${target}/.soai_install_previous.$$.$RANDOM"
    SOAI_INSTALL_PREVIOUS_DIRECTORY="$backup"
    SOAI_INSTALL_ORIGINAL_ENTRIES=()
    local original_entry=""
    while IFS= read -r original_entry; do
        if [ -e "${target}/${original_entry}" ] || [ -L "${target}/${original_entry}" ]; then
            SOAI_INSTALL_ORIGINAL_ENTRIES+=("$original_entry")
        fi
    done < <(soai_install__managed_root_entries)
    if [ -e "${target}/data/vendor" ]; then
        SOAI_INSTALL_ORIGINAL_ENTRIES+=("data/vendor")
    fi
    if ! soai_install__run_noisy_command mkdir -p "$backup"; then
        soai_managed_runtime__die "Failed to create install rollback directory: ${backup}" || return 1
    fi
    if ! soai_install__backup_staged_entries "$target" "$backup" "$staging"; then
        soai_install__rollback_payload "$target" || return 1
        return 1
    fi
    if ! soai_install__move_staged_entries "$target" "$staging"; then
        soai_install__rollback_payload "$target" || return 1
        return 1
    fi
}

soai_install__rollback_payload() {
    local target="$1"
    local backup="${SOAI_INSTALL_PREVIOUS_DIRECTORY:-}"
    soai_install__upgrade_operation "$target" abort || return 1
    if [ -z "$backup" ]; then
        return 0
    fi
    if ! soai_install__restore_managed_entries "$target" "$backup"; then
        soai_managed_runtime__die "Installation recovery failed; originals retained at ${backup}." || return 1
    fi
    SOAI_INSTALL_PREVIOUS_DIRECTORY=""
}

soai_install__commit_payload() {
    local target="$1"
    local backup="${SOAI_INSTALL_PREVIOUS_DIRECTORY:-}"
    if [ -n "$backup" ]; then
        soai_install__remove_path "$target" "$backup" || return 1
        SOAI_INSTALL_PREVIOUS_DIRECTORY=""
    fi
}

soai_install__upgrade_operation() {
    local target="$1"
    local operation="$2"
    local staging="${3:-}"
    if [ "${SOAI_INSTALL_EXISTING_INSTALLATION:-0}" != 1 ] && [ "$operation" != finish ]; then
        return 0
    fi
    local python_executable="${SOAI_VENV_PATH}/bin/python"
    if [ ! -x "$python_executable" ]; then
        python_executable="${target}/soai_main_venv/bin/python"
    fi
    if [ ! -x "$python_executable" ]; then
        soai_managed_runtime__die "The managed Python runtime is required to protect the existing installation." || return 1
    fi
    local -a arguments=("$operation" --base-path "$target" --edition "$SOAI_EXPLICIT_EDITION")
    if [ -n "$staging" ]; then
        arguments+=(--source "$SCRIPT_DIR" --staged "$staging")
    fi
    PYTHONPATH="${SCRIPT_DIR}/backend" SOAI_INSTALL_LOCK_HELD_PATH="$SOAI_INSTALL_LOCK_DIR" \
        soai_install__run_noisy_command "$python_executable" -P -m app.updater.installation_plugin_upgrade "${arguments[@]}"
}

soai_install__backup_staged_entries() {
    local target="$1"
    local backup="$2"
    local staging="$3"
    local entry=""
    while IFS= read -r entry; do
        if [ ! -e "${staging}/${entry}" ]; then
            continue
        fi
        if [ -e "${target}/${entry}" ]; then
            soai_install__run_noisy_command mkdir -p "$(dirname "${backup}/${entry}")" || return 1
            soai_install__run_noisy_command mv "${target}/${entry}" "${backup}/${entry}" || return 1
        fi
    done < <(soai_install__managed_root_entries)
    if [ -e "${staging}/data/vendor" ] && [ -e "${target}/data/vendor" ]; then
        soai_install__run_noisy_command mkdir -p "${backup}/data" || return 1
        soai_install__run_noisy_command mv "${target}/data/vendor" "${backup}/data/vendor" || return 1
    fi
}

soai_install__move_staged_entries() {
    local target="$1"
    local staging="$2"
    local entry=""
    while IFS= read -r entry; do
        if [ -e "${staging}/${entry}" ]; then
            soai_install__run_noisy_command mv "${staging}/${entry}" "${target}/${entry}" || return 1
        fi
    done < <(soai_install__managed_root_entries)
    if [ -e "${staging}/data/vendor" ]; then
        if ! soai_install__run_noisy_command mkdir -p "${target}/data"; then
            soai_managed_runtime__die "Failed to create target data directory: ${target}/data" || return 1
        fi
        soai_install__run_noisy_command mv "${staging}/data/vendor" "${target}/data/vendor" || return 1
    fi
}

soai_install__restore_managed_entries() {
    local target="$1"
    local backup="$2"
    local entry=""
    local original_entry=""
    local originally_present=0
    while IFS= read -r entry; do
        originally_present=0
        for original_entry in "${SOAI_INSTALL_ORIGINAL_ENTRIES[@]}"; do
            if [ "$original_entry" = "$entry" ]; then
                originally_present=1
                break
            fi
        done
        if [ "$originally_present" = 1 ] && [ ! -e "${backup}/${entry}" ]; then
            continue
        fi
        if [ -e "${target}/${entry}" ] || [ -L "${target}/${entry}" ]; then
            soai_install__remove_path "$target" "${target}/${entry}" || return 1
        fi
        if [ -e "${backup}/${entry}" ]; then
            soai_install__run_noisy_command mkdir -p "$(dirname "${target}/${entry}")" || return 1
            soai_install__run_noisy_command mv "${backup}/${entry}" "${target}/${entry}" || return 1
        fi
    done < <(soai_install__managed_root_entries; printf '%s\n' 'data/vendor')
}

soai_install__copy_tree() {
    local source="$1"
    local target="$2"
    soai_install__reject_control_chars "install source" "$source" || return 1
    soai_install__reject_control_chars "install target" "$target" || return 1
    local source_real
    source_real="$(cd "$source" && pwd -P)" || {
        soai_managed_runtime__die "Failed to resolve install source path: ${source}" || return 1
    }
    local target_real=""
    if [ -d "$target" ]; then
        target_real="$(cd "$target" && pwd -P)" || {
            soai_managed_runtime__die "Failed to resolve install target path: ${target}" || return 1
        }
    fi
    if [ -n "$target_real" ] && [ "$source_real" = "$target_real" ]; then
        soai_install__upgrade_operation "$target" prepare "$source" || return 1
        soai_install__write_manifest "$target" "$source" || return 1
        return 0
    fi
    local staging="${target}/.soai_install_staging.$$.$RANDOM"
    soai_install__remove_path "$target" "$staging" || return 1
    if ! soai_install__run_noisy_command mkdir -p "$staging"; then
        soai_managed_runtime__die "Failed to create install staging directory: ${staging}" || return 1
    fi
    if ! soai_install__copy_staging_payload "$source" "$staging"; then
        soai_install__remove_path "$target" "$staging" || true
        return 1
    fi
    if ! soai_install__upgrade_operation "$target" prepare "$staging"; then
        soai_install__remove_path "$target" "$staging" || return 1
        return 1
    fi
    if ! soai_install__replace_managed_entries "$target" "$staging"; then
        soai_install__remove_path "$target" "$staging" || true
        return 1
    fi
    soai_install__remove_path "$target" "$staging" || return 1
    soai_install__write_manifest "$target" "$source" || return 1
}
