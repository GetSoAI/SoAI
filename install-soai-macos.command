#!/usr/bin/env bash

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
        dimensions="$(stty size <&2 2>/dev/null || printf '24 80')"
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
                progress=" ($downloaded/$SOAI_INSTALL_UI_DOWNLOAD_TOTAL bytes)"
                progress_summary="${percentage}%"
            else
                progress_summary="$downloaded bytes"
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
        dimensions="$(stty size <&2 2>/dev/null || printf '24 80')"
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

soai_macos_install__status() {
    if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then
        if [ "${2:-started}" = started ]; then
            soai_install_ui__start "$1"
        else
            soai_install_ui__message "$2" "$1"
        fi
        return
    fi
    printf ">>> %s\n" "$1" >&2
}

soai_macos_install__die() {
    if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then
        soai_install_ui__failure "$*"
        exit 1
    fi
    printf "ERROR: %s\n" "$*" >&2
    exit 1
}

soai_macos_install__cleanup() {
    local original_status="$?"
    if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then soai_install_ui__stop; fi
    if [ -n "${SOAI_MACOS_INSTALL_TEMP_DIR:-}" ] && [ -d "$SOAI_MACOS_INSTALL_TEMP_DIR" ]; then
        if [ "$SOAI_MACOS_INSTALL_USE_SUDO" = "1" ]; then
            sudo rm -rf -- "$SOAI_MACOS_INSTALL_TEMP_DIR"
        else
            rm -rf -- "$SOAI_MACOS_INSTALL_TEMP_DIR"
        fi
    fi
    if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then soai_install_ui__finish "$original_status"; fi
}

soai_macos_install__ask_autostart() {
    SOAI_MACOS_INSTALL_AUTOSTART=0
    case "${SOAI_INSTALL_AUTOSTART:-}" in
        y|Y|yes|YES|Yes)
            SOAI_MACOS_INSTALL_AUTOSTART=1
            return
            ;;
        n|N|no|NO|No)
            return
            ;;
        "") ;;
        *) soai_macos_install__die "SOAI_INSTALL_AUTOSTART must be y or n." ;;
    esac
    if [ ! -r /dev/tty ] || [ ! -w /dev/tty ]; then
        soai_macos_install__status "No interactive terminal is available; automatic startup is disabled." warning
        return
    fi
    local response=""
    if read -r -t 30 -p "Start SoAI automatically at system startup? [y/N] " response < /dev/tty; then
        case "$response" in
            y|Y|yes|YES|Yes) SOAI_MACOS_INSTALL_AUTOSTART=1 ;;
            n|N|no|NO|No|"") ;;
            *) soai_macos_install__status "Unrecognized response; automatic startup is disabled." warning ;;
        esac
    else
        printf "\n" > /dev/tty 2>/dev/null || true
        soai_macos_install__status "No response received within 30 seconds; automatic startup is disabled." warning
    fi
}

soai_macos_install__prepare_elevation() {
    SOAI_MACOS_INSTALL_USE_SUDO=0
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        return
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        soai_macos_install__die "SoAI requires administrator privileges for installation, but sudo is unavailable."
    fi
    soai_macos_install__status "Administrator privileges are required to install SoAI in /Applications/SoAI." information
    soai_install_ui__stop
    sudo -v || soai_macos_install__die "Unable to obtain administrator privileges through sudo."
    SOAI_MACOS_INSTALL_USE_SUDO=1
}

soai_macos_install__run_installer() {
    local installer_path="$1"
    shift
    if [ "$SOAI_MACOS_INSTALL_USE_SUDO" = "1" ]; then
        soai_install_ui__stop
        sudo -v || soai_macos_install__die "Unable to refresh administrator privileges."
        soai_install_ui__delegate sudo bash -c 'unset SOAI_INSTALL_DIAGNOSTICS_DIR SOAI_INSTALL_UI_CONTEXT; export SOAI_INSTALL_UI_HEADER=1 SOAI_INSTALL_UI_PARENT=1; exec bash "$@"' bash "$installer_path" "$@"
    else
        soai_install_ui__stop
        soai_install_ui__delegate bash "$installer_path" "$@"
    fi
}

soai_macos_install__require_commands() {
    local missing_commands=()
    local command_name=""
    if [ "$SOAI_MACOS_INSTALL_AUTOSTART" = "1" ]; then
        if ! command -v launchctl >/dev/null 2>&1 || ! command -v plutil >/dev/null 2>&1; then
            soai_macos_install__die "Automatic startup requires the macOS launchd tools."
        fi
    fi
    if [ -n "$SOAI_MACOS_INSTALL_LOCAL_ROOT" ]; then
        return
    fi
    for command_name in curl osascript shasum unzip; do
        if ! command -v "$command_name" >/dev/null 2>&1; then
            missing_commands+=("$command_name")
        fi
    done
    if [ "${#missing_commands[@]}" -ne 0 ]; then
        soai_macos_install__die "Required macOS commands are unavailable: ${missing_commands[*]}."
    fi
}

soai_macos_install__resolve_local_payload() {
    SOAI_MACOS_INSTALL_LOCAL_ROOT=""
    local source_path="${BASH_SOURCE[0]:-}"
    if [ -z "$source_path" ] || [ ! -f "$source_path" ] || [ -L "$source_path" ]; then
        return
    fi
    local source_root=""
    source_root="$(cd "$(dirname "$source_path")" && pwd -P)"
    local required_file=""
    for required_file in \
        VERSION \
        backend/main.py \
        frontend/index.html \
        plugins/ollama.soaiplugin \
        install-soai-from-release.sh \
        soai.sh
    do
        if [ ! -f "${source_root}/${required_file}" ] || [ -L "${source_root}/${required_file}" ]; then
            return
        fi
    done
    SOAI_MACOS_INSTALL_LOCAL_ROOT="$source_root"
    soai_macos_install__status "Complete local SoAI payload detected; release download will be skipped." information
}

soai_macos_install__download() {
    local url="$1"
    local destination="$2"
    local maximum_bytes="$3"
    local timeout_seconds="$4"
    shift 4
    local resume_archive="${1:-0}"
    if [ "$#" -gt 0 ]; then
        shift
    fi
    local attempt=1
    local delay=2
    local status=0
    local http_status=""
    local range_restarted=0
    local resume_attempt=0
    local curl_arguments=()
    while [ "$attempt" -le 6 ]; do
        resume_attempt=0
        curl_arguments=(
            --silent --fail --show-error --location --proto '=https' --proto-redir '=https'
            --tlsv1.2 --connect-timeout 15 --max-time "$timeout_seconds"
            --max-filesize "$maximum_bytes" --retry 3 --retry-delay 2
            --speed-limit 1024 --speed-time 60 --write-out '%{http_code}'
            --output "$destination"
        )
        if [ "$resume_archive" = "1" ] && [ -s "$destination" ]; then
            curl_arguments+=(--continue-at -)
            resume_attempt=1
        else
            rm -f "$destination" || return $?
        fi
        local curl_status=0
        if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then
            SOAI_INSTALL_UI_DOWNLOAD_PATH="$destination"
            soai_install_ui__start "$SOAI_INSTALL_UI_LABEL"
            soai_install_ui__capture "Download attempt ${attempt}: ${url}" curl "${curl_arguments[@]}" "$@" "$url" || curl_status=$?
            http_status="$(cat "$SOAI_INSTALL_UI_LAST_ATTEMPT/stdout.log")"
        else
            http_status="$(curl "${curl_arguments[@]}" "$@" "$url")" || curl_status=$?
        fi
        if [ "$curl_status" -eq 0 ]; then
            if [ ! -s "$destination" ]; then
                soai_macos_install__die "Downloaded asset is empty: ${url}"
            fi
            return 0
        else
            status=$curl_status
        fi
        soai_macos_install__status "Download attempt ${attempt}/6 failed (curl ${status}, HTTP ${http_status})." warning
        case "$status" in
            5|6|7|18|28|52|55|56|92) ;;
            22|33|36)
                if [ "$resume_attempt" != "1" ] || [ "$range_restarted" = "1" ]; then
                    return "$status"
                fi
                if [ "$status" = "22" ] && [ "$http_status" != "416" ]; then
                    return "$status"
                fi
                range_restarted=1
                rm -f "$destination" || return $?
                ;;
            *) return "$status" ;;
        esac
        if [ "$attempt" -eq 6 ]; then
            return "$status"
        fi
        soai_macos_install__status "Retrying download in ${delay} seconds..."
        sleep "$delay" || return $?
        attempt=$((attempt + 1))
        delay=$((delay * 2))
        if [ "$delay" -gt 30 ]; then
            delay=30
        fi
    done
}

soai_macos_install__resolve_release() {
    local release_json="$SOAI_MACOS_INSTALL_TEMP_DIR/release.json"
    local metadata_path="$SOAI_MACOS_INSTALL_TEMP_DIR/release-metadata.tsv"
    local resolver_path="$SOAI_MACOS_INSTALL_TEMP_DIR/resolve-release.js"
    soai_macos_install__status "Resolving the latest published SoAI release from GitHub..."
    soai_macos_install__download \
        'https://api.github.com/repos/GetSoAI/SoAI/releases/latest' \
        "$release_json" 8388608 120 0 \
        --header 'Accept: application/vnd.github+json' \
        --header 'X-GitHub-Api-Version: 2022-11-28' \
        --user-agent 'SoAI-Installer/1'
    cat > "$resolver_path" <<'JAVASCRIPT'
ObjC.import('Foundation');

function run(arguments) {
    const input = $.NSString.stringWithContentsOfFileEncodingError(arguments[0], $.NSUTF8StringEncoding, null);
    const inputText = ObjC.unwrap(input);
    if (typeof inputText !== 'string') {
        throw new Error('Latest GitHub release metadata is unreadable.');
    }
    const release = JSON.parse(inputText);
    if (release.draft !== false || release.prerelease !== false || !/^v[0-9]+\.[0-9]+\.[0-9]+$/.test(release.tag_name)) {
        throw new Error('Latest GitHub release metadata is invalid.');
    }
    const version = release.tag_name.substring(1);
    const names = [
        `SoAI-${version}-macos-complete.zip`,
        `SoAI-${version}-macos-complete.zip.sha256`
    ];
    const fields = [version];
    for (const name of names) {
        const matches = release.assets.filter((asset) => asset && asset.name === name);
        if (matches.length !== 1) {
            throw new Error(`Latest GitHub release must contain exactly one asset named ${name}.`);
        }
        const asset = matches[0];
        const expectedUrl = `https://github.com/GetSoAI/SoAI/releases/download/${release.tag_name}/${name}`;
        if (asset.browser_download_url !== expectedUrl || !Number.isSafeInteger(asset.size) || asset.size <= 0) {
            throw new Error(`Latest GitHub release asset metadata is invalid: ${name}`);
        }
        fields.push(expectedUrl, String(asset.size));
    }
    return fields.join('\t');
}
JAVASCRIPT
    soai_install_ui__capture "Resolve macOS release metadata" osascript -l JavaScript "$resolver_path" "$release_json"
    cp "$SOAI_INSTALL_UI_LAST_ATTEMPT/stdout.log" "$metadata_path"
    IFS=$'\t' read -r \
        SOAI_MACOS_INSTALL_VERSION \
        SOAI_MACOS_INSTALL_ARCHIVE_URL \
        SOAI_MACOS_INSTALL_ARCHIVE_SIZE \
        SOAI_MACOS_INSTALL_CHECKSUM_URL \
        SOAI_MACOS_INSTALL_CHECKSUM_SIZE < "$metadata_path"
}

soai_macos_install__download_release() {
    SOAI_MACOS_INSTALL_ARCHIVE_PATH="$SOAI_MACOS_INSTALL_TEMP_DIR/SoAI.zip"
    SOAI_MACOS_INSTALL_CHECKSUM_PATH="$SOAI_MACOS_INSTALL_TEMP_DIR/SoAI.zip.sha256"
    soai_macos_install__status "Downloading SoAI ${SOAI_MACOS_INSTALL_VERSION} for macOS..."
    soai_macos_install__download "$SOAI_MACOS_INSTALL_CHECKSUM_URL" "$SOAI_MACOS_INSTALL_CHECKSUM_PATH" 1024 120
    SOAI_INSTALL_UI_DOWNLOAD_TOTAL="${SOAI_MACOS_INSTALL_ARCHIVE_SIZE}"
    soai_macos_install__download "$SOAI_MACOS_INSTALL_ARCHIVE_URL" "$SOAI_MACOS_INSTALL_ARCHIVE_PATH" 2147483648 7200 1
}

soai_macos_install__validate_release() {
    if [ "$(wc -c < "$SOAI_MACOS_INSTALL_ARCHIVE_PATH" | tr -d '[:space:]')" != "$SOAI_MACOS_INSTALL_ARCHIVE_SIZE" ]; then
        soai_macos_install__die "Downloaded SoAI archive size does not match GitHub release metadata."
    fi
    if [ "$(wc -c < "$SOAI_MACOS_INSTALL_CHECKSUM_PATH" | tr -d '[:space:]')" != "$SOAI_MACOS_INSTALL_CHECKSUM_SIZE" ]; then
        soai_macos_install__die "Downloaded SoAI checksum size does not match GitHub release metadata."
    fi
    local archive_name="SoAI-${SOAI_MACOS_INSTALL_VERSION}-macos-complete.zip"
    local expected_hash=""
    local checksum_text=""
    checksum_text="$(cat "$SOAI_MACOS_INSTALL_CHECKSUM_PATH")"
    expected_hash="${checksum_text%%  *}"
    if ! [[ "$expected_hash" =~ ^[0-9a-f]{64}$ ]] || [ "$checksum_text" != "${expected_hash}  ${archive_name}" ]; then
        soai_macos_install__die "SoAI archive checksum sidecar is invalid."
    fi
    local actual_hash=""
    soai_install_ui__capture "Compute macOS archive SHA-256" shasum -a 256 "$SOAI_MACOS_INSTALL_ARCHIVE_PATH"
    actual_hash="$(awk '{print $1}' "$SOAI_INSTALL_UI_LAST_ATTEMPT/stdout.log")"
    if [ "$actual_hash" != "$expected_hash" ]; then
        soai_macos_install__die "SoAI archive checksum verification failed."
    fi
}

soai_macos_install__install() {
    local installer_path=""
    if [ -n "$SOAI_MACOS_INSTALL_LOCAL_ROOT" ]; then
        installer_path="$SOAI_MACOS_INSTALL_LOCAL_ROOT/install-soai-from-release.sh"
    else
        local extraction_path="$SOAI_MACOS_INSTALL_TEMP_DIR/extracted"
        mkdir -p "$extraction_path"
        soai_install_ui__run "Extracting application files" unzip -q "$SOAI_MACOS_INSTALL_ARCHIVE_PATH" -d "$extraction_path"
        installer_path="$extraction_path/SoAI/install-soai-from-release.sh"
    fi
    if [ ! -f "$installer_path" ] || [ -L "$installer_path" ]; then
        soai_macos_install__die "SoAI payload does not contain a regular installer."
    fi
    if [ "$SOAI_MACOS_INSTALL_AUTOSTART" = "1" ]; then
        soai_macos_install__status "Installing SoAI with launchd automatic startup enabled..."
        soai_macos_install__run_installer "$installer_path" --fast
        return
    fi
    soai_macos_install__status "Installing SoAI without a launchd service..."
    soai_macos_install__run_installer "$installer_path" --target /Applications/SoAI
    soai_install_ui__message information "Start SoAI manually with: sudo /Applications/SoAI/soai.command"
}

soai_macos_install__main() {
    set -euo pipefail
    soai_install_ui__init || exit 1
    trap soai_macos_install__cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    if [ "$(uname -s 2>/dev/null || true)" != "Darwin" ]; then
        soai_macos_install__die "This installer supports macOS only."
    fi
    case "$(uname -m 2>/dev/null || true)" in
        arm64|x86_64|amd64) ;;
        *) soai_macos_install__die "This installer supports Intel x86_64 and Apple Silicon macOS only." ;;
    esac
    soai_macos_install__ask_autostart
    soai_macos_install__resolve_local_payload
    soai_macos_install__require_commands
    soai_macos_install__prepare_elevation
    if [ -z "$SOAI_MACOS_INSTALL_LOCAL_ROOT" ]; then
        SOAI_MACOS_INSTALL_TEMP_DIR="$(mktemp -d)"
        trap soai_macos_install__cleanup EXIT
        soai_macos_install__resolve_release
        soai_macos_install__download_release
        SOAI_INSTALL_UI_DOWNLOAD_PATH=""
        SOAI_INSTALL_UI_DOWNLOAD_TOTAL=0
        soai_macos_install__status "Verifying the SoAI release checksum..."
        soai_macos_install__validate_release
        soai_install_ui__message completed "Release downloaded and verified."
    fi
    soai_install_ui__stop
    export SOAI_INSTALL_UI_PARENT=1
    soai_macos_install__install
    if [ -n "$SOAI_MACOS_INSTALL_LOCAL_ROOT" ]; then
        soai_install_ui__message completed "Local SoAI installation completed successfully."
    else
        soai_install_ui__message completed "SoAI ${SOAI_MACOS_INSTALL_VERSION} installation completed successfully."
    fi
}

soai_macos_install__main "$@"
