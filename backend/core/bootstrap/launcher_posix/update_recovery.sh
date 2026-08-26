#!/usr/bin/env bash
# SoAI - POSIX launcher update recovery policy [backend/core/bootstrap/launcher_posix/update_recovery.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_launcher__is_update_preserved_item() {
    local item_name="$1"
    case "$item_name" in
        .soai_update_transaction_*|logs|temp|data|cache|models|backends|config|node_modules|*_venv|*.pyc|__pycache__)
            return 0
            ;;
    esac
    return 1
}

soai_launcher__remove_non_preserved_update_items() {
    local transaction_path="$1"
    local item_path
    local item_name
    shopt -s nullglob dotglob
    for item_path in "${SCRIPT_DIR}"/*; do
        item_name="$(basename "$item_path")"
        if soai_launcher__is_update_preserved_item "$item_name"; then
            continue
        fi
        rm -rf -- "$item_path"
    done
    shopt -u nullglob dotglob
}

soai_launcher__move_update_old_items_back() {
    local old_path="$1"
    local old_item
    local item_name
    local destination_item
    shopt -s nullglob dotglob
    for old_item in "${old_path}"/*; do
        item_name="$(basename "$old_item")"
        destination_item="${SCRIPT_DIR}/${item_name}"
        if [ -e "$destination_item" ] || [ -L "$destination_item" ]; then
            rm -rf -- "$destination_item"
        fi
        mv -- "$old_item" "$destination_item"
    done
    shopt -u nullglob dotglob
}

soai_launcher__path_mtime_epoch() {
    local path="$1"
    if stat -c %Y "$path" >/dev/null 2>&1; then
        stat -c %Y "$path"
        return 0
    fi
    if stat -f %m "$path" >/dev/null 2>&1; then
        stat -f %m "$path"
        return 0
    fi
    return 1
}

soai_launcher__stale_update_lock_without_live_pid() {
    local lock_dir="$1"
    local stale_after_seconds=120
    local modified_ts=""
    local now_ts=""
    local age_seconds=0
    modified_ts="$(soai_launcher__path_mtime_epoch "$lock_dir" 2>/dev/null || true)"
    case "$modified_ts" in
        ''|*[!0-9]*)
            return 1
            ;;
    esac
    now_ts="$(date +%s 2>/dev/null || true)"
    case "$now_ts" in
        ''|*[!0-9]*)
            return 1
            ;;
    esac
    age_seconds=$((now_ts - modified_ts))
    [ "$age_seconds" -ge "$stale_after_seconds" ]
}

soai_launcher__update_lock_active() {
    local lock_dir="${SCRIPT_DIR}/data/locks/soai.update.lock.d"
    local pid_file="${lock_dir}/pid"
    local lock_pid
    if [ ! -d "$lock_dir" ]; then
        return 1
    fi
    if [ ! -f "$pid_file" ]; then
        if soai_launcher__stale_update_lock_without_live_pid "$lock_dir"; then
            rmdir -- "$lock_dir" >/dev/null 2>&1 || return 0
            return 1
        fi
        return 0
    fi
    lock_pid="$(cat "$pid_file" 2>/dev/null || true)"
    case "$lock_pid" in
        ''|*[!0-9]*)
            if soai_launcher__stale_update_lock_without_live_pid "$lock_dir"; then
                rm -f -- "$pid_file" >/dev/null 2>&1 || return 0
                rmdir -- "$lock_dir" >/dev/null 2>&1 || return 0
                return 1
            fi
            return 0
            ;;
    esac
    if kill -0 "$lock_pid" >/dev/null 2>&1; then
        return 0
    fi
    rm -f -- "$pid_file" >/dev/null 2>&1 || true
    rmdir -- "$lock_dir" >/dev/null 2>&1 || true
    return 1
}

soai_launcher__recover_update_transactions() {
    local transaction_path
    local old_path
    shopt -s nullglob
    for transaction_path in "${SCRIPT_DIR}"/.soai_update_transaction_*; do
        [ -d "$transaction_path" ] || continue
        if soai_launcher__update_lock_active; then
            echo "ERROR: SoAI software update is in progress; startup recovery is deferred." >&2
            shopt -u nullglob
            return 1
        fi
        if [ -f "${transaction_path}/success_complete" ]; then
            rm -rf -- "$transaction_path"
            continue
        fi
        if [ ! -f "${transaction_path}/rollback_required" ]; then
            rm -rf -- "$transaction_path"
            continue
        fi
        old_path="${transaction_path}/old"
        if [ ! -d "$old_path" ]; then
            echo "ERROR: Cannot recover update transaction without rollback directory: ${transaction_path}" >&2
            shopt -u nullglob
            return 1
        fi
        if [ -f "${transaction_path}/old_complete" ]; then
            soai_launcher__remove_non_preserved_update_items "$transaction_path"
        fi
        soai_launcher__move_update_old_items_back "$old_path" || {
            shopt -u nullglob
            return 1
        }
        rm -rf -- "$transaction_path"
    done
    shopt -u nullglob
}
