#!/usr/bin/env bash
# SoAI - Installation presentation and retained command diagnostics [backend/core/bootstrap/launcher_posix/install_presentation.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

soai_install_ui__sanitize() {
    LC_ALL=C sed -E \
        -e $'s/\033\\][^\007\033]*(\007|\033\\\\)//g' \
        -e $'s/\033\\[[0-9;?]*[ -/]*[@-~]//g' \
        -e 's#(https?://)[^/@[:space:]]+@#\1[REDACTED]@#g' \
        -e 's/([Aa][Uu][Tt][Hh][Oo][Rr][Ii][Zz][Aa][Tt][Ii][Oo][Nn]:[[:space:]]*).*/\1[REDACTED]/g' \
        -e 's/([?&]([Tt][Oo][Kk][Ee][Nn]|[Kk][Ee][Yy]|[Aa][Pp][Ii]_[Kk][Ee][Yy]|[Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd]|[Ss][Ee][Cc][Rr][Ee][Tt])=)[^&[:space:]]*/\1[REDACTED]/g' \
        -e 's/(([Tt][Oo][Kk][Ee][Nn]|[Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd]|[Ss][Ee][Cc][Rr][Ee][Tt]|[Aa][Pp][Ii]_[Kk][Ee][Yy])[[:space:]]*[:=][[:space:]]*)[^[:space:]]+/\1[REDACTED]/g' | LC_ALL=C tr -d '\000-\010\013\014\016-\037\177' | tr '\r' '\n'
}

soai_install_ui__validate_directory() {
    local directory="$1"
    local identity=""
    [ -d "$directory" ] && [ ! -L "$directory" ] || return 1
    case "$directory" in /var/tmp/soai-install.*) ;; *) return 1 ;; esac
    [ "$(dirname "$directory")" = /var/tmp ] || return 1
    if [ "$(uname -s)" = Darwin ]; then
        identity="$(stat -f '%u:%Lp' "$directory")" || return 1
    else
        identity="$(stat -c '%u:%a' "$directory")" || return 1
    fi
    [ "$identity" = "$(id -u):700" ]
}

soai_install_ui__init() {
    SOAI_INSTALL_UI_ENABLED=0
    SOAI_INSTALL_UI_ACTIVE=0
    SOAI_INSTALL_UI_NESTED="${SOAI_INSTALL_UI_PARENT:-0}"
    SOAI_INSTALL_UI_SPINNER_PID=""
    SOAI_INSTALL_UI_LABEL="Checking system requirements"
    SOAI_INSTALL_UI_PHASE=""
    SOAI_INSTALL_UI_DOWNLOAD_PATH=""
    SOAI_INSTALL_UI_DOWNLOAD_TOTAL=0
    SOAI_INSTALL_UI_COMMAND_PID=""
    SOAI_INSTALL_UI_COMMAND_GROUP_FILE=""
    SOAI_INSTALL_UI_LAST_ATTEMPT=""
    SOAI_INSTALL_UI_LAST_CHECK=""
    SOAI_INSTALL_UI_STARTED=$SECONDS
    SOAI_INSTALL_UI_ORANGE=""
    SOAI_INSTALL_UI_GREEN=""
    SOAI_INSTALL_UI_LIGHT_GRAY=""
    SOAI_INSTALL_UI_DIM=""
    SOAI_INSTALL_UI_YELLOW=""
    SOAI_INSTALL_UI_RED=""
    SOAI_INSTALL_UI_RESET=""
    SOAI_INSTALL_UI_CHECK='+'
    SOAI_INSTALL_UI_CROSS='x'
    SOAI_INSTALL_UI_SEPARATOR=' -'
    case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in
        *UTF-8*|*utf-8*|*utf8*|*UTF8*) SOAI_INSTALL_UI_CHECK='✓'; SOAI_INSTALL_UI_CROSS='✗'; SOAI_INSTALL_UI_SEPARATOR=' ·' ;;
    esac
    if [ -n "${SOAI_INSTALL_DIAGNOSTICS_DIR:-}" ]; then
        if ! soai_install_ui__validate_directory "$SOAI_INSTALL_DIAGNOSTICS_DIR"; then
            printf 'ERROR: Refusing an unsafe installer diagnostic directory.\n' >&2
            return 1
        fi
    else
        SOAI_INSTALL_DIAGNOSTICS_DIR="$(umask 077; mktemp -d /var/tmp/soai-install.XXXXXXXX)" || return 1
        chmod u=rwx,go=,u-s,g-s,o-t "$SOAI_INSTALL_DIAGNOSTICS_DIR" || {
            printf 'ERROR: Could not protect installer diagnostics at %s.\n' "$SOAI_INSTALL_DIAGNOSTICS_DIR" >&2
            return 1
        }
    fi
    local log_identity=""
    if [ -e "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log" ] || [ -L "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log" ]; then
        [ -f "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log" ] && [ ! -L "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log" ] || {
            printf 'ERROR: Refusing an unsafe installer diagnostic log.\n' >&2
            return 1
        }
        if [ "$(uname -s)" = Darwin ]; then
            log_identity="$(stat -f '%u:%Lp' "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log")" || return 1
        else
            log_identity="$(stat -c '%u:%a' "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log")" || return 1
        fi
        [ "$log_identity" = "$(id -u):600" ] || {
            printf 'ERROR: Installer diagnostic log ownership or permissions are unsafe.\n' >&2
            return 1
        }
    fi
    export SOAI_INSTALL_DIAGNOSTICS_DIR
    export SOAI_INSTALL_UI_CONTEXT=1
    (umask 077; touch "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log") || return 1
    if [ -t 2 ] && [ "${TERM:-dumb}" != dumb ] && [ -z "${NO_COLOR+x}" ]; then
        SOAI_INSTALL_UI_ORANGE=$'\033[33m'
        if command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || printf 0)" -ge 256 ]; then
            SOAI_INSTALL_UI_ORANGE=$'\033[38;5;215m'
        fi
        SOAI_INSTALL_UI_GREEN=$'\033[32m'
        SOAI_INSTALL_UI_LIGHT_GRAY=$'\033[90m'
        SOAI_INSTALL_UI_DIM=$'\033[2m'
        SOAI_INSTALL_UI_YELLOW=$'\033[33m'
        SOAI_INSTALL_UI_RED=$'\033[31m'
        SOAI_INSTALL_UI_RESET=$'\033[0m'
    fi
    SOAI_INSTALL_UI_ENABLED=1
    if [ "${SOAI_INSTALL_UI_HEADER:-0}" != 1 ] \
        && [ "${SOAI_INSTALL_SILENT:-0}" != 1 ] && [ "${SOAI_INSTALL_JSON_EVENTS:-0}" != 1 ]; then
        printf '\nSo%sAI%s Installer%s%s%s%s %s %s %s%s\n\n' "$SOAI_INSTALL_UI_GREEN" "$SOAI_INSTALL_UI_RESET" "$SOAI_INSTALL_UI_RESET" "$SOAI_INSTALL_UI_DIM" "$SOAI_INSTALL_UI_SEPARATOR" "$SOAI_INSTALL_UI_RESET" "$SOAI_INSTALL_UI_LIGHT_GRAY" "$(uname -s)" "$(uname -m)" "$SOAI_INSTALL_UI_RESET" >&2
    fi
    export SOAI_INSTALL_UI_HEADER=1
}

soai_install_ui__stop() {
    SOAI_INSTALL_UI_ACTIVE=0
    if [ -n "${SOAI_INSTALL_UI_SPINNER_PID:-}" ]; then
        kill "$SOAI_INSTALL_UI_SPINNER_PID" 2>/dev/null || true
        wait "$SOAI_INSTALL_UI_SPINNER_PID" 2>/dev/null || true
        SOAI_INSTALL_UI_SPINNER_PID=""
        printf '\r\033[K' >&2
    fi
}

soai_install_ui__frame_loop() {
    trap 'exit 0' TERM INT HUP
    local -a frames=('-' '\' '|' '/')
    if [ "$SOAI_INSTALL_UI_CHECK" = '✓' ]; then
        frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    fi
    local index=0
    local width=80
    local dimensions=""
    local elapsed=0
    local line=""
    local progress=""
    local progress_summary=""
    local downloaded=0
    local narrow_line_shown=0
    while true; do
        dimensions="$(trap '' TTOU; stty size <&2 2>/dev/null || printf '24 80')"
        width="${dimensions##* }"
        case "$width" in ''|0|*[!0-9]*) width=80 ;; esac
        elapsed=$((SECONDS - SOAI_INSTALL_UI_STARTED))
        progress=""
        progress_summary=""
        if [ -n "$SOAI_INSTALL_UI_DOWNLOAD_PATH" ] && [ -f "$SOAI_INSTALL_UI_DOWNLOAD_PATH" ]; then
            downloaded="$(wc -c < "$SOAI_INSTALL_UI_DOWNLOAD_PATH")"
            if [ "$SOAI_INSTALL_UI_DOWNLOAD_TOTAL" -gt 0 ]; then
                local percentage=$((downloaded * 100 / SOAI_INSTALL_UI_DOWNLOAD_TOTAL))
                if [ "$percentage" -gt 100 ]; then percentage=100; fi
                printf -v progress ' (%d.%02d/%d.%02d MB)' \
                    "$((downloaded / 1000000))" "$((downloaded % 1000000 / 10000))" \
                    "$((SOAI_INSTALL_UI_DOWNLOAD_TOTAL / 1000000))" "$((SOAI_INSTALL_UI_DOWNLOAD_TOTAL % 1000000 / 10000))"
                progress_summary="${percentage}%"
            else
                printf -v progress_summary '%d.%02d MB' "$((downloaded / 1000000))" "$((downloaded % 1000000 / 10000))"
            fi
        fi
        local suffix="${SOAI_INSTALL_UI_SEPARATOR} $(printf '%02d:%02d' "$((elapsed / 60))" "$((elapsed % 60))")"
        if [ -n "$progress_summary" ]; then suffix="${SOAI_INSTALL_UI_SEPARATOR} ${progress_summary}${suffix}"; fi
        line="${SOAI_INSTALL_UI_LABEL}${progress}"
        line="${line:0:$((width > 12 ? width - 6 - ${#suffix} : 0))}${suffix}"
        if [ "$width" -lt 40 ]; then
            if [ "$narrow_line_shown" = 0 ]; then
                printf '\r%s\033[K' "${SOAI_INSTALL_UI_LABEL:0:$((width > 1 ? width - 1 : 0))}" >&2
                narrow_line_shown=1
            fi
        else
            narrow_line_shown=0
            printf '\r%s%s%s %s\033[K' "$SOAI_INSTALL_UI_ORANGE" "${frames[$index]}" "$SOAI_INSTALL_UI_RESET" "$line" >&2
        fi
        index=$(((index + 1) % ${#frames[@]}))
        sleep 0.25
    done
}

soai_install_ui__start() {
    soai_install_ui__stop
    SOAI_INSTALL_UI_ACTIVE=1
    SOAI_INSTALL_UI_LABEL="$1"
    while [[ "$SOAI_INSTALL_UI_LABEL" = *. ]]; do SOAI_INSTALL_UI_LABEL="${SOAI_INSTALL_UI_LABEL%.}"; done
    SOAI_INSTALL_UI_STARTED=$SECONDS
    [ "${SOAI_INSTALL_JSON_EVENTS:-0}" != 1 ] && [ "${SOAI_INSTALL_SILENT:-0}" != 1 ] || return 0
    local dimensions=""
    local width=80
    if [ -t 2 ] && [ "${TERM:-dumb}" != dumb ]; then
        dimensions="$(trap '' TTOU; stty size <&2 2>/dev/null || printf '24 80')"
        width="${dimensions##* }"
        case "$width" in ''|0|*[!0-9]*) width=80 ;; esac
        if [ "$width" -ge 40 ]; then
            soai_install_ui__frame_loop &
            SOAI_INSTALL_UI_SPINNER_PID=$!
            return 0
        fi
    fi
    printf '  %s...\n' "$SOAI_INSTALL_UI_LABEL" >&2
}

soai_install_ui__message() {
    local state="$1"
    local message="$2"
    soai_install_ui__stop
    local color="$SOAI_INSTALL_UI_GREEN"
    local indicator="$SOAI_INSTALL_UI_CHECK"
    case "$state" in
        information) color="$SOAI_INSTALL_UI_ORANGE"; indicator='>' ;;
        warning) color="$SOAI_INSTALL_UI_YELLOW"; indicator='!' ;;
        failed) color="$SOAI_INSTALL_UI_RED"; indicator="$SOAI_INSTALL_UI_CROSS" ;;
    esac
    printf '%s: %s\n' "$state" "$message" | soai_install_ui__sanitize >> "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log" || return 1
    if [ "$state" = warning ] || [ "$state" = failed ] \
        || { [ "${SOAI_INSTALL_JSON_EVENTS:-0}" != 1 ] && [ "${SOAI_INSTALL_SILENT:-0}" != 1 ]; }; then
        local safe_message=""
        safe_message="$(printf '%s' "$message" | soai_install_ui__sanitize)" || return 1
        printf '%s%s%s %s\n' "$color" "$indicator" "$SOAI_INSTALL_UI_RESET" "$safe_message" >&2
    fi
}

soai_install_ui__capture() {
    local label="$1"
    shift
    local attempt=""
    attempt="$(umask 077; mktemp -d "$SOAI_INSTALL_DIAGNOSTICS_DIR/attempt.XXXXXXXX")" || return 1
    local status=0
    local identity=""
    printf -v identity '%q ' "$@"
    label="$label: $identity"
    SOAI_INSTALL_UI_LAST_CHECK="$label"
    SOAI_INSTALL_UI_LAST_ATTEMPT="$attempt"
    (umask 077; touch "$attempt/stdout.log" "$attempt/stderr.log") || return 1
    SOAI_INSTALL_UI_COMMAND_GROUP_FILE="$attempt/process-group.txt"
    soai_install_ui__execute "$attempt/stdout.log" "$attempt/stderr.log" "$@" || status=$?
    local stream=""
    for stream in stdout stderr; do
        soai_install_ui__sanitize < "$attempt/$stream.log" > "$attempt/$stream.safe" || return 1
        mv "$attempt/$stream.safe" "$attempt/$stream.log" || return 1
    done
    {
        printf '\nTime: %s\nCheck: %s\nExit code: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$label" "$status"
        cat "$attempt/stdout.log" "$attempt/stderr.log"
    } | soai_install_ui__sanitize >> "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log" || return 1
    printf '%s\n' "$label" | soai_install_ui__sanitize > "$attempt/check.txt" || return 1
    printf '%s\n' "$status" > "$attempt/exit-code.txt" || return 1
    if [ "$status" -ne 0 ]; then
        (umask 077; printf '%s\n%s\n' "$label" "$status" | soai_install_ui__sanitize > "$SOAI_INSTALL_DIAGNOSTICS_DIR/last-command.txt") || return 1
        if [ ! -f "$SOAI_INSTALL_DIAGNOSTICS_DIR/failure.txt" ]; then
            (umask 077; cat "$attempt/stdout.log" "$attempt/stderr.log" > "$SOAI_INSTALL_DIAGNOSTICS_DIR/excerpt.log") || return 1
        fi
    fi
    local warning_file=""
    for warning_file in "$SOAI_INSTALL_DIAGNOSTICS_DIR"/warning.*; do
        [ -f "$warning_file" ] || continue
        case "$warning_file" in *.shown) continue ;; esac
        [ ! -e "$warning_file.shown" ] || continue
        soai_install_ui__message warning "$(cat "$warning_file")" || return 1
        (umask 077; touch "$warning_file.shown") || return 1
    done
    chmod 600 "$attempt"/* "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log" || return 1
    return "$status"
}

soai_install_ui__run() {
    local label="$1"
    shift
    if [ "${SOAI_INSTALL_UI_ACTIVE:-0}" != 1 ] || [ "$SOAI_INSTALL_UI_LABEL" != "$label" ]; then
        soai_install_ui__start "$label"
    fi
    local status=0
    soai_install_ui__capture "$label" "$@" || status=$?
    if [ "$status" -ne 0 ]; then soai_install_ui__stop; fi
    return "$status"
}

soai_install_ui__failure() {
    local message="$1"
    local status="${2:-1}"
    soai_install_ui__stop
    [ ! -e "$SOAI_INSTALL_DIAGNOSTICS_DIR/reported" ] || return 0
    soai_install_ui__message failed "$message" || return 1
    local check_file="$SOAI_INSTALL_DIAGNOSTICS_DIR/failure.txt"
    if [ ! -f "$check_file" ]; then
        check_file="$SOAI_INSTALL_DIAGNOSTICS_DIR/last-command.txt"
    fi
    if [ -f "$check_file" ]; then
        printf '  Check: %s\n  Exit code: %s\n' "$(sed -n '1p' "$check_file")" "$(sed -n '2p' "$check_file")" >&2
    else
        printf '  Exit code: %s\n' "$status" >&2
    fi
    if [ -f "$SOAI_INSTALL_DIAGNOSTICS_DIR/excerpt.log" ]; then
        printf '\n' >&2
        soai_install_ui__sanitize < "$SOAI_INSTALL_DIAGNOSTICS_DIR/excerpt.log" | awk '
            NF {
                if ($0 ~ /^Traceback \(most recent call last\):/) traceback = 1
                last_line = $0
                excerpt_lines[line_count % 12] = $0
                line_count++
            }
            END {
                if (traceback) print last_line
                else for (line_index = (line_count > 12 ? line_count - 12 : 0); line_index < line_count; line_index++) print excerpt_lines[line_index % 12]
            }
        ' | cut -c 1-160 >&2
        printf '  Diagnostic excerpt; full output is retained below.\n' >&2
    fi
    local read_command=""
    printf -v read_command 'cat -- %q' "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log"
    if [ "$(id -u)" = 0 ]; then
        case "${SOAI_INSTALL_UI_READ_METHOD:-${SUDO_USER:+sudo}}" in
            sudo) read_command="sudo $read_command" ;;
            su) printf -v read_command 'su -s /bin/bash root -c %q' "$read_command" ;;
        esac
    fi
    printf '\n  Full log: %s/install.log\n  Read log: %s\n\n' "$SOAI_INSTALL_DIAGNOSTICS_DIR" "$read_command" >&2
    (umask 077; touch "$SOAI_INSTALL_DIAGNOSTICS_DIR/reported") || return 1
}

soai_install_ui__finish() {
    local status="$1"
    soai_install_ui__stop
    if [ -n "${SOAI_INSTALL_UI_COMMAND_PID:-}" ]; then
        kill -TERM "$SOAI_INSTALL_UI_COMMAND_PID" 2>/dev/null || true
        local deadline=$((SECONDS + 5))
        while kill -0 "$SOAI_INSTALL_UI_COMMAND_PID" 2>/dev/null && [ "$SECONDS" -lt "$deadline" ]; do sleep 0.1; done
        if kill -0 "$SOAI_INSTALL_UI_COMMAND_PID" 2>/dev/null; then
            local group=""
            group="$(cat "$SOAI_INSTALL_UI_COMMAND_GROUP_FILE" 2>/dev/null || true)"
            case "$group" in
                ''|*[!0-9]*) ;;
                *) kill -KILL -- "-$group" 2>/dev/null || true ;;
            esac
            kill -KILL "$SOAI_INSTALL_UI_COMMAND_PID" 2>/dev/null || true
        fi
        wait "$SOAI_INSTALL_UI_COMMAND_PID" 2>/dev/null || true
        if [ -n "${SOAI_INSTALL_UI_LAST_ATTEMPT:-}" ]; then
            local stream=""
            for stream in stdout stderr; do
                soai_install_ui__sanitize < "$SOAI_INSTALL_UI_LAST_ATTEMPT/$stream.log" > "$SOAI_INSTALL_UI_LAST_ATTEMPT/$stream.safe" || return 1
                mv "$SOAI_INSTALL_UI_LAST_ATTEMPT/$stream.safe" "$SOAI_INSTALL_UI_LAST_ATTEMPT/$stream.log" || return 1
            done
            {
                printf '\nTime: %s\nCheck: %s\nExit code: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$SOAI_INSTALL_UI_LAST_CHECK" "$status"
                cat "$SOAI_INSTALL_UI_LAST_ATTEMPT/stdout.log" "$SOAI_INSTALL_UI_LAST_ATTEMPT/stderr.log"
            } | soai_install_ui__sanitize >> "$SOAI_INSTALL_DIAGNOSTICS_DIR/install.log" || return 1
            (umask 077; printf '%s\n' "$status" > "$SOAI_INSTALL_UI_LAST_ATTEMPT/exit-code.txt") || return 1
            (umask 077; printf '%s\n' "$SOAI_INSTALL_UI_LAST_CHECK" | soai_install_ui__sanitize > "$SOAI_INSTALL_UI_LAST_ATTEMPT/check.txt") || return 1
            chmod 600 "$SOAI_INSTALL_UI_LAST_ATTEMPT"/* || return 1
        fi
        SOAI_INSTALL_UI_COMMAND_PID=""
    fi
    if [ "$status" -eq 0 ]; then
        return 0
    fi
    [ ! -e "$SOAI_INSTALL_DIAGNOSTICS_DIR/reported" ] || return 0
    case "$status" in
        129|130|141|143)
            soai_install_ui__message warning "Installation cancelled (exit ${status}); diagnostics retained at ${SOAI_INSTALL_DIAGNOSTICS_DIR}/install.log." || return 1
            (umask 077; touch "$SOAI_INSTALL_DIAGNOSTICS_DIR/reported") || return 1
            ;;
        *) soai_install_ui__failure "Installation failed during ${SOAI_INSTALL_UI_LABEL}." "$status" ;;
    esac
}

soai_install_ui__stage() {
    local stage="$1"
    local state="$2"
    local message="$3"
    local label="$message"
    case "$stage" in
        preflight) label="Checking system requirements" ;;
        copy) label="Installing application files" ;;
        managed-runtime) label="Preparing the Python environment" ;;
        soaibench-opencl) label="Checking optional runtime components" ;;
        runtime-artifacts) label="Preparing runtime components" ;;
        migration-hook) label="Finalizing installation" ;;
        autostart) label="Configuring automatic startup" ;;
        dependencies) soai_install_ui__stop; return 0 ;;
        complete)
            soai_install_ui__stop
            if [ "${SOAI_INSTALL_UI_NESTED:-0}" = 1 ]; then return 0; fi
            ;;
    esac
    case "$state" in
        started) soai_install_ui__start "$label" ;;
        completed)
            if [ "$stage" = complete ] || [ "$stage" = autostart ]; then
                soai_install_ui__message completed "$message"
            else
                case "$stage" in
                    preflight) message="System requirements checked" ;;
                    copy) message="Application files installed" ;;
                    managed-runtime) message="Python environment prepared" ;;
                    soaibench-opencl) message="Optional runtime components checked" ;;
                    runtime-artifacts) message="Runtime components prepared" ;;
                    migration-hook) message="Installation finalized" ;;
                esac
                soai_install_ui__message completed "$message"
            fi
            ;;
        failed) soai_install_ui__failure "$message" ;;
    esac
}

soai_install_ui__execute() {
    local stdout_path="$1"
    local stderr_path="$2"
    shift 2
    local status=0
    (
        umask 077
        set -m
        local command_pid=""
        trap 'if [ -n "$command_pid" ]; then kill -TERM -- "-$command_pid" 2>/dev/null || true; wait "$command_pid" 2>/dev/null || true; fi; exit 143' TERM HUP
        trap 'if [ -n "$command_pid" ]; then kill -TERM -- "-$command_pid" 2>/dev/null || true; wait "$command_pid" 2>/dev/null || true; fi; exit 130' INT
        if [ -t 0 ]; then
            "$@" </dev/null &
        else
            "$@" <&0 &
        fi
        command_pid=$!
        set +m
        printf '%s\n' "$command_pid" > "$SOAI_INSTALL_UI_COMMAND_GROUP_FILE"
        wait "$command_pid"
    ) > "$stdout_path" 2> "$stderr_path" <&0 &
    SOAI_INSTALL_UI_COMMAND_PID=$!
    wait "$SOAI_INSTALL_UI_COMMAND_PID" || status=$?
    SOAI_INSTALL_UI_COMMAND_PID=""
    return "$status"
}

soai_install_ui__delegate() {
    soai_install_ui__stop
    local control_directory=""
    control_directory="$(umask 077; mktemp -d "$SOAI_INSTALL_DIAGNOSTICS_DIR/delegate.XXXXXXXX")" || return 1
    SOAI_INSTALL_UI_COMMAND_GROUP_FILE="$control_directory/process-group.txt"
    SOAI_INSTALL_UI_LAST_ATTEMPT=""
    local status=0
    set -m
    "$@" <&0 &
    SOAI_INSTALL_UI_COMMAND_PID=$!
    set +m
    (umask 077; printf '%s\n' "$SOAI_INSTALL_UI_COMMAND_PID" > "$SOAI_INSTALL_UI_COMMAND_GROUP_FILE") || return 1
    wait "$SOAI_INSTALL_UI_COMMAND_PID" || status=$?
    SOAI_INSTALL_UI_COMMAND_PID=""
    if [ "$status" -ne 0 ] && [ "$status" -le 128 ]; then
        (umask 077; touch "$SOAI_INSTALL_DIAGNOSTICS_DIR/reported") || return 1
    fi
    return "$status"
}
