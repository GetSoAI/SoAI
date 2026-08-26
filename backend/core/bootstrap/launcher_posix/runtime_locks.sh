#!/usr/bin/env bash
# SoAI - POSIX launcher runtime installation lock coordination [backend/core/bootstrap/launcher_posix/runtime_locks.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_managed_runtime__refresh_lock_wait_state() {
    local lock_dir="$1"
    local pid_file="$2"
    local now_ts="$3"
    local missing_pid_seen_ts="$4"
    SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS="$missing_pid_seen_ts"
    if [ ! -d "$lock_dir" ]; then
        SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS=""
        return 1
    fi
    if [ -f "$pid_file" ]; then
        local existing_pid
        existing_pid="$(cat "$pid_file" 2>/dev/null || true)"
        if [ -n "$existing_pid" ] && ! kill -0 "$existing_pid" >/dev/null 2>&1; then
            rm -f "$pid_file" >/dev/null 2>&1 || true
            rmdir "$lock_dir" >/dev/null 2>&1 || true
            SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS=""
            return 1
        fi
        if [ -n "$existing_pid" ]; then
            SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS=""
            return 0
        fi
        if [ -z "$missing_pid_seen_ts" ]; then
            SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS="$now_ts"
            return 0
        fi
        if [ $((now_ts - missing_pid_seen_ts)) -ge 5 ]; then
            rm -f "$pid_file" >/dev/null 2>&1 || true
            rmdir "$lock_dir" >/dev/null 2>&1 || true
            SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS=""
            return 1
        fi
        return 0
    fi
    if [ -z "$missing_pid_seen_ts" ]; then
        SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS="$now_ts"
        return 0
    fi
    if [ $((now_ts - missing_pid_seen_ts)) -ge 5 ]; then
        rmdir "$lock_dir" >/dev/null 2>&1 || true
        SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS=""
        return 1
    fi
    return 0
}

soai_managed_runtime__acquire_lock_dir() {
    local lock_dir="$1"
    local pid_file="${lock_dir}/pid"
    local start_ts
    start_ts="$(date +%s)"
    local missing_pid_seen_ts=""
    while true; do
        if mkdir "$lock_dir" >/dev/null 2>&1; then
            if ! printf "%s\n" "$$" > "$pid_file"; then
                rmdir "$lock_dir" >/dev/null 2>&1
                soai_managed_runtime__die "Failed to write lock pid file: ${pid_file}" || return 1
            fi
            return 0
        fi
        local now_ts
        now_ts="$(date +%s)"
        if ! soai_managed_runtime__refresh_lock_wait_state "$lock_dir" "$pid_file" "$now_ts" "$missing_pid_seen_ts"; then
            missing_pid_seen_ts="$SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS"
            continue
        fi
        missing_pid_seen_ts="$SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS"
        local elapsed=$((now_ts - start_ts))
        if [ "$elapsed" -ge 1200 ]; then
            soai_managed_runtime__die "Timed out waiting for lock: ${lock_dir}" || return 1
        fi
        sleep 1
    done
}

soai_managed_runtime__release_lock_dir() {
    local lock_dir="$1"
    rm -f "${lock_dir}/pid" >/dev/null 2>&1
    rmdir "$lock_dir" >/dev/null 2>&1
}

soai_managed_runtime__lock_dir_is_process_owned() {
    local lock_dir="$1"
    local expected_pid="$2"
    local pid_file="${lock_dir}/pid"
    if [ -z "$expected_pid" ] || [ ! -f "$pid_file" ]; then
        return 1
    fi
    local existing_pid
    existing_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [ "$existing_pid" = "$expected_pid" ] && kill -0 "$existing_pid" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

soai_managed_runtime__lock_dir_has_live_owner() {
    local lock_dir="$1"
    local pid_file="${lock_dir}/pid"
    if [ ! -d "$lock_dir" ]; then
        return 1
    fi
    if [ ! -f "$pid_file" ]; then
        return 0
    fi
    local existing_pid
    existing_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [ -n "$existing_pid" ] && kill -0 "$existing_pid" >/dev/null 2>&1; then
        return 0
    fi
    rm -f "$pid_file" >/dev/null 2>&1
    rmdir "$lock_dir" >/dev/null 2>&1
    return 1
}

soai_managed_runtime__wait_for_lock_dir_clear() {
    local lock_dir="$1"
    local pid_file="${lock_dir}/pid"
    local start_ts
    start_ts="$(date +%s)"
    local missing_pid_seen_ts=""
    while [ -d "$lock_dir" ]; do
        local now_ts
        now_ts="$(date +%s)"
        if ! soai_managed_runtime__refresh_lock_wait_state "$lock_dir" "$pid_file" "$now_ts" "$missing_pid_seen_ts"; then
            missing_pid_seen_ts="$SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS"
            continue
        fi
        missing_pid_seen_ts="$SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS"
        local elapsed=$((now_ts - start_ts))
        if [ "$elapsed" -ge 1200 ]; then
            soai_managed_runtime__die "Timed out waiting for lock to clear: ${lock_dir}" || return 1
        fi
        sleep 1
    done
}

soai_managed_runtime__wait_for_install_barriers() {
    local install_marker="$1"
    local install_lock_dir="$2"
    local wait_for_marker="$3"
    local wait_for_lock="$4"
    local wait_context="$5"
    local install_lock_pid_file="${install_lock_dir}/pid"
    local wait_started
    wait_started="$(date +%s)"
    local missing_pid_started=""
    while true; do
        local wait_now
        wait_now="$(date +%s)"
        local marker_active=0
        local lock_active=0
        if [ "$wait_for_marker" = "1" ] && [ -f "$install_marker" ]; then
            marker_active=1
        fi
        if [ "$wait_for_lock" = "1" ] && [ -d "$install_lock_dir" ]; then
            lock_active=1
        fi
        if [ "$marker_active" = "0" ] && [ "$lock_active" = "0" ]; then
            break
        fi
        if [ "$lock_active" = "1" ] \
            && ! soai_managed_runtime__refresh_lock_wait_state "$install_lock_dir" "$install_lock_pid_file" "$wait_now" "$missing_pid_started"; then
            missing_pid_started="$SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS"
            lock_active=0
            if [ "$marker_active" = "0" ]; then
                break
            fi
        elif [ "$lock_active" = "1" ]; then
            missing_pid_started="$SOAI_MANAGED_RUNTIME_LOCK_MISSING_PID_SEEN_TS"
        fi
        if [ $((wait_now - wait_started)) -ge 1200 ]; then
            soai_managed_runtime__die "Timed out waiting for SoAI install to finish in ${wait_context}" || return 1
        fi
        sleep 1
    done
}
