#!/usr/bin/env bash
# SoAI - POSIX launcher systemd service installation [backend/core/bootstrap/launcher_posix/install_service.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_install__systemd_is_supported() {
    if [ "$(uname -s 2>/dev/null || true)" != "Linux" ]; then
        return 1
    fi
    if [ ! -d "/run/systemd/system" ]; then
        return 1
    fi
    command -v systemctl >/dev/null 2>&1
}

soai_install__elevate_prefix() {
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        return 0
    fi
    if command -v sudo >/dev/null 2>&1; then
        printf "sudo"
        return 0
    fi
    return 1
}

soai_install__write_systemd_unit() {
    local target="$1"
    local launcher_path="${target}/${SOAI_EXPLICIT_LAUNCHER_RELATIVE_PATH}"
    if [ -n "${SOAI_EXPLICIT_SYSTEMD_MANAGED_MARKER:-}" ]; then
        printf "%s\n" "# soai.service"
        printf "%s\n" "# ${SOAI_EXPLICIT_SYSTEMD_MANAGED_MARKER}. Manual edits may be overwritten."
    fi
    cat <<UNIT
[Unit]
Description=SoAI - Smart Orchestrator for Artificial Intelligence
Documentation=https://soai.io/docs
After=network-online.target docker.service nvidia-persistenced.service
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=${target}
ExecStart=${launcher_path} start
Restart=on-failure
RestartSec=10
KillSignal=SIGTERM
TimeoutStartSec=0
TimeoutStopSec=90
StandardOutput=journal
StandardError=journal
SyslogIdentifier=soai
UNIT
    cat <<UNIT
Environment="SOAI_NO_BROWSER=1"
Environment="PYTHONUNBUFFERED=1"
UNIT
    cat <<UNIT

[Install]
WantedBy=multi-user.target
UNIT
}

soai_install__install_systemd_service() {
    local target="$1"
    if ! soai_install__systemd_is_supported; then
        soai_managed_runtime__die "--fast requires systemd on Linux so SoAI can auto-start and be verified." || return 1
    fi
    local elevate=""
    elevate="$(soai_install__elevate_prefix || true)"
    if [ -z "$elevate" ] && [ "${EUID:-$(id -u)}" -ne 0 ]; then
        soai_managed_runtime__die "systemd detected but sudo is unavailable. Re-run --fast as root." || return 1
    fi
    local unit_path="/etc/systemd/system/soai.service"
    soai_launcher__info "Installing systemd service: ${unit_path}"
    if [ -z "$elevate" ]; then
        soai_install__write_systemd_unit "$target" > "$unit_path" || return 1
        systemctl daemon-reload || {
            soai_managed_runtime__die "systemctl daemon-reload failed after writing ${unit_path}." || return 1
        }
        if [ "${SOAI_INSTALL_DEFER_SERVICE_START:-0}" = "1" ]; then
            systemctl enable soai.service || {
                soai_managed_runtime__die "Failed to enable soai.service via systemctl." || return 1
            }
        else
            systemctl enable --now soai.service || {
                soai_managed_runtime__die "Failed to enable/start soai.service via systemctl." || return 1
            }
        fi
    else
        soai_install__write_systemd_unit "$target" | "$elevate" tee "$unit_path" >/dev/null || return 1
        "$elevate" systemctl daemon-reload || {
            soai_managed_runtime__die "systemctl daemon-reload failed after writing ${unit_path}." || return 1
        }
        if [ "${SOAI_INSTALL_DEFER_SERVICE_START:-0}" = "1" ]; then
            "$elevate" systemctl enable soai.service || {
                soai_managed_runtime__die "Failed to enable soai.service via systemctl." || return 1
            }
        else
            "$elevate" systemctl enable --now soai.service || {
                soai_managed_runtime__die "Failed to enable/start soai.service via systemctl." || return 1
            }
        fi
    fi
}

soai_install__launchd_is_supported() {
    [ "$(uname -s 2>/dev/null || true)" = "Darwin" ] \
        && command -v launchctl >/dev/null 2>&1 \
        && command -v plutil >/dev/null 2>&1
}

soai_install__write_launchd_plist() {
    local target="$1"
    local launcher_path="${target}/${SOAI_EXPLICIT_LAUNCHER_RELATIVE_PATH}"
    cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.getsoai.soai</string>
    <key>ProgramArguments</key>
    <array>
        <string>${launcher_path}</string>
        <string>start</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${target}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>SOAI_NO_BROWSER</key>
        <string>1</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>StandardOutPath</key>
    <string>${target}/data/logs/soai-launchd.log</string>
    <key>StandardErrorPath</key>
    <string>${target}/data/logs/soai-launchd.log</string>
</dict>
</plist>
PLIST
}

soai_install__install_launchd_service() {
    local target="$1"
    if ! soai_install__launchd_is_supported; then
        soai_managed_runtime__die "--fast requires launchd on macOS so SoAI can auto-start and be verified." || return 1
    fi
    local elevate=()
    if [ "${EUID:-$(id -u)}" -ne 0 ]; then
        if ! command -v sudo >/dev/null 2>&1; then
            soai_managed_runtime__die "launchd requires administrator privileges and sudo is unavailable." || return 1
        fi
        elevate=(sudo)
    fi
    local plist_path="/Library/LaunchDaemons/com.getsoai.soai.plist"
    local temporary_path="${plist_path}.$$"
    soai_launcher__info "Installing launchd service: ${plist_path}"
    "${elevate[@]}" mkdir -p "${target}/data/logs" || return 1
    soai_install__write_launchd_plist "$target" | "${elevate[@]}" tee "$temporary_path" >/dev/null || {
        "${elevate[@]}" rm -f "$temporary_path"
        return 1
    }
    "${elevate[@]}" plutil -lint "$temporary_path" >/dev/null || {
        "${elevate[@]}" rm -f "$temporary_path"
        return 1
    }
    "${elevate[@]}" chown root:wheel "$temporary_path" || {
        "${elevate[@]}" rm -f "$temporary_path"
        return 1
    }
    "${elevate[@]}" chmod 0644 "$temporary_path" || {
        "${elevate[@]}" rm -f "$temporary_path"
        return 1
    }
    "${elevate[@]}" mv -f "$temporary_path" "$plist_path" || {
        "${elevate[@]}" rm -f "$temporary_path"
        return 1
    }
    if [ "${SOAI_INSTALL_DEFER_SERVICE_START:-0}" = "1" ]; then
        return 0
    fi
    if "${elevate[@]}" launchctl print system/com.getsoai.soai >/dev/null 2>&1; then
        "${elevate[@]}" launchctl bootout system/com.getsoai.soai || return 1
    fi
    "${elevate[@]}" launchctl bootstrap system "$plist_path" || return 1
    "${elevate[@]}" launchctl kickstart -k system/com.getsoai.soai || return 1
}

soai_install__install_system_service() {
    case "$(uname -s 2>/dev/null || true)" in
        Linux) soai_install__install_systemd_service "$1" ;;
        Darwin) soai_install__install_launchd_service "$1" ;;
        *) soai_managed_runtime__die "Automatic startup is unsupported on this platform." || return 1 ;;
    esac
}

soai_install__runtime_base_url() {
    local target="$1"
    local runtime_record
    runtime_record="$(soai_install__target_temp_dir "$target")/soai.pid"
    local python_executable="${target}/soai_main_venv/bin/python"
    if [ ! -x "$python_executable" ] || [ ! -f "$runtime_record" ]; then
        return 1
    fi
    "$python_executable" -c 'import json,sys; record=json.load(open(sys.argv[1],encoding="utf-8")); endpoint=record["api_endpoint"]; assert set(record)=={"schema_version","runtime_id","edition","pid","process_create_time_ns","base_dir","started_at_epoch_ms","api_endpoint"} and record["schema_version"]==1 and record["edition"]==sys.argv[2] and set(endpoint)=={"bind_host","scheme","preferred_port","effective_port"} and endpoint["scheme"] in {"http","https"} and isinstance(endpoint["preferred_port"],int) and 1 <= endpoint["preferred_port"] <= 65535 and isinstance(endpoint["effective_port"],int) and 1 <= endpoint["effective_port"] <= 65535; host="127.0.0.1" if endpoint["bind_host"]=="0.0.0.0" else "::1" if endpoint["bind_host"]=="::" else endpoint["bind_host"]; host=f"[{host}]" if ":" in host and not host.startswith("[") else host; print("{}://{}:{}".format(endpoint["scheme"],host,endpoint["effective_port"]))' "$runtime_record" "$SOAI_EXPLICIT_EDITION" 2>/dev/null
}

soai_install__runtime_health_url() {
    local target="$1"
    local base_url
    base_url="$(soai_install__runtime_base_url "$target")" || return 1
    printf "%s/api/v1/system/health" "$base_url"
}

soai_install__probe_health_once() {
    local target="$1"
    local health_url
    health_url="$(soai_install__runtime_health_url "$target")" || return 1
    if command -v curl >/dev/null 2>&1; then
        case "$health_url" in
            https://127.0.0.1:*|https://\[::1\]:*)
                curl --insecure -fsS --max-time 2 "$health_url" >/dev/null 2>&1
                ;;
            *)
                curl -fsS --max-time 2 "$health_url" >/dev/null 2>&1
                ;;
        esac
        return
    fi
    if command -v wget >/dev/null 2>&1; then
        case "$health_url" in
            https://127.0.0.1:*|https://\[::1\]:*)
                wget --no-check-certificate -q -T 2 -O /dev/null "$health_url" >/dev/null 2>&1
                ;;
            *)
                wget -q -T 2 -O /dev/null "$health_url" >/dev/null 2>&1
                ;;
        esac
        return
    fi
    return 1
}

soai_install__wait_for_health() {
    local target="$1"
    local timeout_sec="180"
    local sleep_sec="2"
    local started
    started="$(date +%s)"
    while true; do
        if soai_install__probe_health_once "$target"; then
            return 0
        fi
        local now
        now="$(date +%s)"
        if [ $((now - started)) -ge "$timeout_sec" ]; then
            local health_url
            health_url="$(soai_install__runtime_health_url "$target" || true)"
            if [ -n "$health_url" ]; then
                soai_managed_runtime__die "SoAI service started but health check did not become ready at ${health_url}." || return 1
            fi
            soai_managed_runtime__die "SoAI service started but did not publish an authoritative runtime health endpoint." || return 1
        fi
        sleep "$sleep_sec"
    done
}

soai_install__post_install_fast() {
    local target="$1"
    soai_install__emit_stage "$target" "install" "autostart" "started" "Installing and starting SoAI system service..." || return 1
    soai_install__install_system_service "$target" || {
        soai_install__emit_stage "$target" "install" "autostart" "failed" "SoAI system service installation or startup failed." || true
        return 1
    }
    if [ "${SOAI_INSTALL_DEFER_SERVICE_START:-0}" = "1" ]; then
        soai_install__emit_stage "$target" "install" "autostart" "completed" "SoAI system service is installed and enabled; startup is deferred." || return 1
        return 0
    fi
    soai_install__wait_for_health "$target" || {
        soai_install__emit_stage "$target" "install" "autostart" "failed" "SoAI service did not pass its startup health check." || true
        return 1
    }
    soai_install__emit_stage "$target" "install" "autostart" "completed" "SoAI service is running and healthy." || return 1
    if [ "${SOAI_INSTALL_SILENT:-0}" != "1" ]; then
        local base_url
        base_url="$(soai_install__runtime_base_url "$target")" || {
            soai_managed_runtime__die "SoAI service is healthy but its authoritative runtime endpoint is unavailable." || return 1
        }
        soai_launcher__info "SoAI is installed and running. Open: ${base_url}"
    fi
}
