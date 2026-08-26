#!/usr/bin/env bash
# SoAI - POSIX launcher installation payload selection [backend/core/bootstrap/launcher_posix/install_payload.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_install__managed_root_entries() {
    printf "%s\n" \
        backend \
        frontend \
        plugins \
        licenses \
        docs \
        VERSION \
        release-info-v1.json \
        CHANGE-DATES.md \
        COMMERCIAL-LICENSING-AVAILABILITY.md \
        COMMERCIAL-LICENSE.md \
        COMMERCIAL-SUPPORT-TERMS.md \
        LICENSE.md \
        README.md \
        NOTICE \
        LICENSING.md \
        PRIVACY.md \
        ORGANIZATION-EVALUATION-TERMS.md \
        DOCUMENTATION.md \
        SECURITY.md \
        RELEASE_NOTES.md \
        requirements.txt \
        install-soai-macos.command \
        install-soai-windows.ps1 \
        install-soai-linux.sh \
        soai.sh \
        soai.command \
        soai.exe \
        install-soai-from-release.sh \
        install-soai-from-release.command \
        install-soai-from-release.bat \
        uninstall-soai-linux.sh
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
    rm -rf -- "$path" || return 1
}

soai_install__copy_existing_entry() {
    local source_entry="$1"
    local target_parent="$2"
    if [ ! -e "$source_entry" ]; then
        return 0
    fi
    if ! mkdir -p "$target_parent"; then
        soai_managed_runtime__die "Failed to create install staging directory: ${target_parent}" || return 1
    fi
    if ! cp -pPR "$source_entry" "$target_parent/"; then
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
}

soai_install__replace_managed_entries() {
    local target="$1"
    local staging="$2"
    local backup="${target}/.soai_install_previous.$$.$RANDOM"
    soai_install__remove_path "$target" "$backup" || return 1
    if ! mkdir -p "$backup"; then
        soai_managed_runtime__die "Failed to create install rollback directory: ${backup}" || return 1
    fi
    if ! soai_install__backup_staged_entries "$target" "$backup" "$staging"; then
        soai_install__restore_managed_entries "$target" "$backup" || true
        soai_install__remove_path "$target" "$backup" || true
        return 1
    fi
    if ! soai_install__move_staged_entries "$target" "$staging"; then
        soai_install__restore_managed_entries "$target" "$backup" || true
        soai_install__remove_path "$target" "$backup" || true
        return 1
    fi
    soai_install__remove_path "$target" "$backup" || return 1
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
            mkdir -p "$(dirname "${backup}/${entry}")" || return 1
            mv "${target}/${entry}" "${backup}/${entry}" || return 1
        fi
    done < <(soai_install__managed_root_entries)
    if [ -e "${staging}/data/vendor" ] && [ -e "${target}/data/vendor" ]; then
        mkdir -p "${backup}/data" || return 1
        mv "${target}/data/vendor" "${backup}/data/vendor" || return 1
    fi
}

soai_install__move_staged_entries() {
    local target="$1"
    local staging="$2"
    local entry=""
    while IFS= read -r entry; do
        if [ -e "${staging}/${entry}" ]; then
            mv "${staging}/${entry}" "${target}/${entry}" || return 1
        fi
    done < <(soai_install__managed_root_entries)
    if [ -e "${staging}/data/vendor" ]; then
        if ! mkdir -p "${target}/data"; then
            soai_managed_runtime__die "Failed to create target data directory: ${target}/data" || return 1
        fi
        mv "${staging}/data/vendor" "${target}/data/vendor" || return 1
    fi
}

soai_install__restore_managed_entries() {
    local target="$1"
    local backup="$2"
    local entry=""
    while IFS= read -r entry; do
        if [ -e "${target}/${entry}" ]; then
            soai_install__remove_path "$target" "${target}/${entry}" || return 1
        fi
        if [ -e "${backup}/${entry}" ]; then
            mv "${backup}/${entry}" "${target}/${entry}" || return 1
        fi
    done < <(soai_install__managed_root_entries)
    if [ -e "${target}/data/vendor" ]; then
        soai_install__remove_path "$target" "${target}/data/vendor" || return 1
    fi
    if [ -e "${backup}/data/vendor" ]; then
        mkdir -p "${target}/data" || return 1
        mv "${backup}/data/vendor" "${target}/data/vendor" || return 1
    fi
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
        soai_install__write_manifest "$target" "$source" || return 1
        return 0
    fi
    local staging="${target}/.soai_install_staging.$$.$RANDOM"
    soai_install__remove_path "$target" "$staging" || return 1
    if ! mkdir -p "$staging"; then
        soai_managed_runtime__die "Failed to create install staging directory: ${staging}" || return 1
    fi
    if ! soai_install__copy_staging_payload "$source" "$staging"; then
        soai_install__remove_path "$target" "$staging" || true
        return 1
    fi
    if ! soai_install__replace_managed_entries "$target" "$staging"; then
        soai_install__remove_path "$target" "$staging" || true
        return 1
    fi
    soai_install__remove_path "$target" "$staging" || return 1
    soai_install__write_manifest "$target" "$source" || return 1
}
