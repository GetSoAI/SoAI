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

soai_bootstrap__status() {
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

soai_bootstrap__die() {
    if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then
        soai_install_ui__failure "$*"
        exit 1
    fi
    printf "ERROR: %s\n" "$*" >&2
    exit 1
}

soai_bootstrap__cleanup() {
    local original_status="$?"
    if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then soai_install_ui__stop; fi
    if [ "${SOAI_BOOTSTRAP_COMMAND_CREATED:-0}" = "1" ] \
        && [ -L "${SOAI_BOOTSTRAP_COMMAND_PATH:-}" ] \
        && [ "$(readlink "$SOAI_BOOTSTRAP_COMMAND_PATH")" = "${SOAI_BOOTSTRAP_COMMAND_TARGET:-}" ]; then
        "${SOAI_BOOTSTRAP_ELEVATE[@]}" rm -f -- "$SOAI_BOOTSTRAP_COMMAND_PATH" || \
            soai_bootstrap__status "Failed to roll back the SoAI command: ${SOAI_BOOTSTRAP_COMMAND_PATH}" warning
    fi
    if [ -n "${SOAI_BOOTSTRAP_TEMP_DIR:-}" ] && [ -d "$SOAI_BOOTSTRAP_TEMP_DIR" ]; then
        if ! "${SOAI_BOOTSTRAP_ELEVATE[@]}" rm -rf -- "$SOAI_BOOTSTRAP_TEMP_DIR"; then
            soai_bootstrap__status "Could not remove temporary installation files at ${SOAI_BOOTSTRAP_TEMP_DIR}. Remove this directory with administrator privileges." warning
        fi
    fi
    if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ]; then soai_install_ui__finish "$original_status"; fi
    return "$original_status"
}

soai_bootstrap__ask_autostart() {
    SOAI_BOOTSTRAP_AUTOSTART=0
    case "${SOAI_INSTALL_AUTOSTART:-}" in
        y|Y|yes|YES|Yes)
            SOAI_BOOTSTRAP_AUTOSTART=1
            return
            ;;
        n|N|no|NO|No)
            return
            ;;
        "") ;;
        *) soai_bootstrap__die "SOAI_INSTALL_AUTOSTART must be y or n." ;;
    esac
    if [ ! -r /dev/tty ] || [ ! -w /dev/tty ]; then
        soai_bootstrap__status "No interactive terminal is available; automatic startup is disabled." warning
        return
    fi
    local response=""
    if read -r -t 30 -p "Start SoAI automatically at system startup? [y/N] " response < /dev/tty; then
        case "$response" in
            y|Y|yes|YES|Yes) SOAI_BOOTSTRAP_AUTOSTART=1 ;;
            n|N|no|NO|No|"") ;;
            *) soai_bootstrap__status "Unrecognized response; automatic startup is disabled." warning ;;
        esac
    else
        printf "\n" > /dev/tty 2>/dev/null || true
        soai_bootstrap__status "No response received within 30 seconds; automatic startup is disabled." warning
    fi
}

soai_bootstrap__sudo_permits_command() {
    local sudo_probe_output=""
    if sudo_probe_output="$(LC_ALL=C sudo -n -l -- "$@" 2>&1)"; then
        return 0
    fi
    case "$sudo_probe_output" in
        *"a password is required"*|*"interactive authentication is required"*) return 0 ;;
    esac
    return 1
}

soai_bootstrap__write_root_script() {
    local script_path="$1"
    local -a bootstrap_functions=()
    mapfile -t bootstrap_functions < <(compgen -A function | sed -n -e '/^soai_bootstrap__/p' -e '/^soai_install_ui__/p')
    {
        printf '#!/usr/bin/env bash\n'
        declare -f "${bootstrap_functions[@]}"
        printf 'soai_bootstrap__main "$@"\n'
    } > "$script_path"
}

soai_bootstrap__rerun_as_root() {
    local elevation_method="$1"
    shift
    local attempts=1
    if [ "$elevation_method" = "su" ]; then
        if ! (exec 3</dev/tty) 2>/dev/null; then
            soai_bootstrap__status "su requires an interactive terminal to read the root password." warning
            return 0
        fi
        attempts=3
    fi
    local elevation_directory=""
    elevation_directory="$(mktemp -d)" || soai_bootstrap__die "Could not create a temporary directory for root privilege elevation."
    local script_path=""
    if [ -n "$SOAI_BOOTSTRAP_LOCAL_ROOT" ]; then
        script_path="${SOAI_BOOTSTRAP_LOCAL_ROOT}/$(basename "${BASH_SOURCE[0]}")"
    else
        script_path="${elevation_directory}/install_soai_linux.sh"
        soai_bootstrap__write_root_script "$script_path"
    fi
    local autostart_answer="n"
    if [ "$SOAI_BOOTSTRAP_AUTOSTART" = "1" ]; then
        autostart_answer="y"
    fi
    local -a forwarded_environment=("PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" "SOAI_INSTALL_AUTOSTART=${autostart_answer}" "SOAI_INSTALL_UI_HEADER=1" "SOAI_INSTALL_UI_READ_METHOD=su")
    local proxy_variable=""
    local proxy_value=""
    for proxy_variable in http_proxy https_proxy ftp_proxy all_proxy no_proxy HTTP_PROXY HTTPS_PROXY FTP_PROXY ALL_PROXY NO_PROXY; do
        if proxy_value="$(printenv "$proxy_variable")"; then
            forwarded_environment+=("${proxy_variable}=${proxy_value}")
        fi
    done
    local root_command=""
    root_command="$(printf '%q ' touch -- "${elevation_directory}/started")&& exec $(printf '%q ' env -u SOAI_INSTALL_DIAGNOSTICS_DIR -u SOAI_INSTALL_UI_CONTEXT -u SOAI_INSTALL_UI_PARENT "${forwarded_environment[@]}" bash "$script_path" "$@")"
    local attempt=1
    local status=0
    soai_install_ui__stop
    trap ':' INT
    while [ "$attempt" -le "$attempts" ]; do
        status=0
        if [ "$elevation_method" = "sudo-su" ]; then
            soai_bootstrap__status "Obtaining root privileges through sudo su." information
            soai_install_ui__stop
            sudo su -s /bin/bash root -c "$root_command" || status=$?
        else
            soai_bootstrap__status "Enter the root password for su (attempt ${attempt}/${attempts})." information
            soai_install_ui__stop
            su -s /bin/bash root -c "$root_command" </dev/tty || status=$?
        fi
        if [ -e "${elevation_directory}/started" ] || [ "$status" -gt 128 ]; then
            if [ "${SOAI_INSTALL_UI_ENABLED:-0}" = 1 ] && [ -e "${elevation_directory}/started" ] && [ "$status" -ne 0 ]; then
                (umask 077; touch "$SOAI_INSTALL_DIAGNOSTICS_DIR/reported") || { rm -rf -- "$elevation_directory"; exit 1; }
            fi
            rm -rf -- "$elevation_directory"
            exit "$status"
        fi
        attempt=$((attempt + 1))
    done
    trap - INT
    rm -rf -- "$elevation_directory"
    soai_bootstrap__status "Could not obtain root privileges through ${elevation_method}." warning
}

soai_bootstrap__prepare_elevation() {
    SOAI_BOOTSTRAP_ELEVATE=()
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        return
    fi
    soai_bootstrap__status "Root privileges are required to install SoAI in /opt/soai." information
    soai_install_ui__stop
    if command -v sudo >/dev/null 2>&1 && sudo -v; then
        if soai_bootstrap__sudo_permits_command bash -c true; then
            SOAI_BOOTSTRAP_ELEVATE=(sudo)
            return
        fi
        if command -v su >/dev/null 2>&1 \
            && soai_bootstrap__sudo_permits_command su -s /bin/bash root -c true; then
            soai_bootstrap__rerun_as_root sudo-su "$@"
        fi
    fi
    if command -v su >/dev/null 2>&1; then
        soai_bootstrap__rerun_as_root su "$@"
    fi
    soai_bootstrap__die "SoAI requires root privileges for installation, but neither sudo nor su could provide them. Run the installer as root."
}

soai_bootstrap__require_autostart_support() {
    if [ "$SOAI_BOOTSTRAP_AUTOSTART" != "1" ]; then
        return
    fi
    if [ ! -d /run/systemd/system ] || ! command -v systemctl >/dev/null 2>&1; then
        soai_bootstrap__die "Automatic startup requires a running systemd service manager."
    fi
}

soai_bootstrap__install_path_command() {
    SOAI_BOOTSTRAP_COMMAND_PATH="/usr/local/bin/soai"
    SOAI_BOOTSTRAP_COMMAND_TARGET="/opt/soai/soai.sh"
    SOAI_BOOTSTRAP_COMMAND_CREATED=0
    if [ -L "$SOAI_BOOTSTRAP_COMMAND_PATH" ]; then
        if [ "$(readlink "$SOAI_BOOTSTRAP_COMMAND_PATH")" = "$SOAI_BOOTSTRAP_COMMAND_TARGET" ]; then
            soai_bootstrap__status "SoAI command is already installed: ${SOAI_BOOTSTRAP_COMMAND_PATH}" completed
            return 0
        fi
        soai_bootstrap__die "Refusing to replace an existing symbolic link: ${SOAI_BOOTSTRAP_COMMAND_PATH}"
    fi
    if [ -e "$SOAI_BOOTSTRAP_COMMAND_PATH" ]; then
        soai_bootstrap__die "Refusing to replace an existing path: ${SOAI_BOOTSTRAP_COMMAND_PATH}"
    fi
    "${SOAI_BOOTSTRAP_ELEVATE[@]}" install -d -m 0755 "$(dirname "$SOAI_BOOTSTRAP_COMMAND_PATH")"
    "${SOAI_BOOTSTRAP_ELEVATE[@]}" ln -s -- "$SOAI_BOOTSTRAP_COMMAND_TARGET" "$SOAI_BOOTSTRAP_COMMAND_PATH" || \
        soai_bootstrap__die "Failed to install the SoAI command: ${SOAI_BOOTSTRAP_COMMAND_PATH}"
    SOAI_BOOTSTRAP_COMMAND_CREATED=1
    soai_bootstrap__status "Installed SoAI command: ${SOAI_BOOTSTRAP_COMMAND_PATH}" completed
}

soai_bootstrap__resolve_local_payload() {
    SOAI_BOOTSTRAP_LOCAL_ROOT=""
    local source_path="${BASH_SOURCE[0]:-}"
    if [ -z "$source_path" ] || [ ! -f "$source_path" ] || [ -L "$source_path" ]; then
        return
    fi
    local source_root=""
    source_root="$(cd "$(dirname "$source_path")" && pwd -P)"
    local local_installer="install_soai_from_release.sh"
    if [ -f "${source_root}/backend/core/bootstrap/filename_digests.json" ] && [ -f "${source_root}/install-soai-from-release.sh" ]; then
        local_installer="install-soai-from-release.sh"
    fi
    local required_file=""
    for required_file in \
        VERSION \
        backend/main.py \
        frontend/index.html \
        plugins/ollama.soaiplugin \
        "$local_installer" \
        soai.sh
    do
        if [ ! -f "${source_root}/${required_file}" ] || [ -L "${source_root}/${required_file}" ]; then
            return
        fi
    done
    SOAI_BOOTSTRAP_LOCAL_ROOT="$source_root"
    soai_bootstrap__status "Complete local SoAI payload detected; release download will be skipped." information
}

soai_bootstrap__install_prerequisites() {
    if [ -n "$SOAI_BOOTSTRAP_LOCAL_ROOT" ]; then
        return
    fi
    local missing_commands=()
    local command_name=""
    local required_commands=(curl openssl python3 unzip)
    for command_name in "${required_commands[@]}"; do
        if ! command -v "$command_name" >/dev/null 2>&1; then
            missing_commands+=("$command_name")
        fi
    done
    local required_packages=()
    for command_name in "${missing_commands[@]}"; do
        case "$command_name" in
            curl) required_packages+=(curl ca-certificates) ;;
            openssl) required_packages+=(openssl ca-certificates) ;;
            python3) required_packages+=(python3) ;;
            unzip) required_packages+=(unzip) ;;
        esac
    done
    if [ ! -s /etc/ssl/certs/ca-certificates.crt ]; then
        required_packages+=(ca-certificates)
    fi
    if [ "${#required_packages[@]}" -eq 0 ]; then
        return
    fi
    if ! command -v apt-get >/dev/null 2>&1; then
        soai_bootstrap__die "Missing required commands or CA certificates. Install them and run the installer again: ${required_packages[*]}."
    fi
    soai_bootstrap__status "Installing bootstrap prerequisites: ${required_packages[*]}"
    soai_install_ui__run "Installing bootstrap prerequisites" "${SOAI_BOOTSTRAP_ELEVATE[@]}" env DEBIAN_FRONTEND=noninteractive apt-get update
    soai_install_ui__run "Installing bootstrap prerequisites" "${SOAI_BOOTSTRAP_ELEVATE[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install \
        -y --no-install-recommends "${required_packages[@]}"
}

soai_bootstrap__download() {
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
                soai_bootstrap__die "Downloaded asset is empty: ${url}"
            fi
            return 0
        else
            status=$curl_status
        fi
        soai_bootstrap__status "Download attempt ${attempt}/6 failed (curl ${status}, HTTP ${http_status})." warning
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
        soai_bootstrap__status "Retrying download in ${delay} seconds..."
        sleep "$delay" || return $?
        attempt=$((attempt + 1))
        delay=$((delay * 2))
        if [ "$delay" -gt 30 ]; then
            delay=30
        fi
    done
}

soai_bootstrap__resolve_release() {
    local release_json="$SOAI_BOOTSTRAP_TEMP_DIR/release.json"
    local metadata_path="$SOAI_BOOTSTRAP_TEMP_DIR/release-metadata.tsv"
    soai_bootstrap__status "Resolving the latest published SoAI release from GitHub..."
    soai_bootstrap__download \
        'https://api.github.com/repos/GetSoAI/SoAI/releases/latest' \
        "$release_json" 8388608 120 0 \
        --header 'Accept: application/vnd.github+json' \
        --header 'X-GitHub-Api-Version: 2022-11-28' \
        --user-agent 'SoAI-Installer/1'
    soai_install_ui__capture "Release metadata parsing" python3 - "$release_json" "$metadata_path" "$SOAI_BOOTSTRAP_PLATFORM" <<'PYTHON'
import json
import re
import sys

release_path, metadata_path, platform = sys.argv[1:]
with open(release_path, "r", encoding="utf-8") as release_file:
    release = json.load(release_file)
if not isinstance(release, dict) or release.get("draft") is not False:
    raise SystemExit("Latest GitHub release metadata is invalid.")
if release.get("prerelease") is not False:
    raise SystemExit("The latest GitHub release is a prerelease.")
tag = release.get("tag_name")
if not isinstance(tag, str) or re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) is None:
    raise SystemExit("Latest GitHub release tag is invalid.")
version = tag[1:]
expected_names = (
    f"SoAI-{version}-release-manifest-v1.json",
    f"SoAI-{version}-release-manifest-v1.json.sig",
    f"SoAI-{version}-linux-complete.zip",
    f"SoAI-{version}-linux-complete.zip.sha256",
)
assets = release.get("assets")
if not isinstance(assets, list):
    raise SystemExit("Latest GitHub release assets are invalid.")
resolved = {}
for asset in assets:
    if not isinstance(asset, dict):
        raise SystemExit("Latest GitHub release asset entry is invalid.")
    name = asset.get("name")
    if name not in expected_names:
        continue
    if name in resolved:
        raise SystemExit(f"Latest GitHub release contains duplicate asset: {name}")
    url = asset.get("browser_download_url")
    size = asset.get("size")
    expected_prefix = f"https://github.com/GetSoAI/SoAI/releases/download/{tag}/"
    if not isinstance(url, str) or url != f"{expected_prefix}{name}":
        raise SystemExit(f"Latest GitHub release asset URL is invalid: {name}")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise SystemExit(f"Latest GitHub release asset size is invalid: {name}")
    resolved[name] = (url, size)
missing = [name for name in expected_names if name not in resolved]
if missing:
    raise SystemExit(f"Latest GitHub release is missing required assets: {', '.join(missing)}")
fields = [version, tag, platform]
for name in expected_names:
    url, size = resolved[name]
    fields.extend((url, str(size)))
if any("\t" in field or "\n" in field for field in fields):
    raise SystemExit("Latest GitHub release metadata contains control characters.")
with open(metadata_path, "w", encoding="utf-8", newline="\n") as metadata_file:
    metadata_file.write("\t".join(fields) + "\n")
PYTHON
    IFS=$'\t' read -r \
        SOAI_BOOTSTRAP_VERSION \
        _ \
        SOAI_BOOTSTRAP_RESOLVED_PLATFORM \
        SOAI_BOOTSTRAP_MANIFEST_URL \
        SOAI_BOOTSTRAP_MANIFEST_SIZE \
        SOAI_BOOTSTRAP_SIGNATURE_URL \
        SOAI_BOOTSTRAP_SIGNATURE_SIZE \
        SOAI_BOOTSTRAP_ARCHIVE_URL \
        SOAI_BOOTSTRAP_ARCHIVE_SIZE \
        SOAI_BOOTSTRAP_CHECKSUM_URL \
        SOAI_BOOTSTRAP_CHECKSUM_SIZE < "$metadata_path"
}

soai_bootstrap__download_release() {
    SOAI_BOOTSTRAP_MANIFEST_PATH="$SOAI_BOOTSTRAP_TEMP_DIR/manifest.json"
    SOAI_BOOTSTRAP_SIGNATURE_PATH="$SOAI_BOOTSTRAP_TEMP_DIR/manifest.sig"
    SOAI_BOOTSTRAP_ARCHIVE_PATH="$SOAI_BOOTSTRAP_TEMP_DIR/SoAI.zip"
    SOAI_BOOTSTRAP_CHECKSUM_PATH="$SOAI_BOOTSTRAP_TEMP_DIR/SoAI.zip.sha256"
    soai_bootstrap__status "Downloading SoAI ${SOAI_BOOTSTRAP_VERSION}..."
    soai_bootstrap__download "$SOAI_BOOTSTRAP_MANIFEST_URL" "$SOAI_BOOTSTRAP_MANIFEST_PATH" 67108864 120
    soai_bootstrap__download "$SOAI_BOOTSTRAP_SIGNATURE_URL" "$SOAI_BOOTSTRAP_SIGNATURE_PATH" 1024 120
    soai_bootstrap__download "$SOAI_BOOTSTRAP_CHECKSUM_URL" "$SOAI_BOOTSTRAP_CHECKSUM_PATH" 1024 120
    SOAI_INSTALL_UI_DOWNLOAD_TOTAL="${SOAI_BOOTSTRAP_ARCHIVE_SIZE}"
    soai_bootstrap__download "$SOAI_BOOTSTRAP_ARCHIVE_URL" "$SOAI_BOOTSTRAP_ARCHIVE_PATH" 2147483648 7200 1
}

soai_bootstrap__verify_signature() {
    local public_key_path="$SOAI_BOOTSTRAP_TEMP_DIR/release-public-key.pem"
    local signature_binary_path="$SOAI_BOOTSTRAP_TEMP_DIR/manifest-signature.bin"
    soai_install_ui__capture "Release signature decoding" python3 - "$public_key_path" "$SOAI_BOOTSTRAP_SIGNATURE_PATH" "$signature_binary_path" <<'PYTHON'
import base64
import hashlib
import sys

public_key_path, signature_path, signature_binary_path = sys.argv[1:]
public_key = base64.b64decode("CGaMOT/YiAPhi/5WKUJuLlwOeQ50JI/ibWmduxiHzNI=", validate=True)
expected_fingerprint = "e0333589b1ca792397182cc3f843989c021a056c61e281f8456c1da4f479f2a7"
if len(public_key) != 32 or hashlib.sha256(public_key).hexdigest() != expected_fingerprint:
    raise SystemExit("Embedded SoAI release public key is invalid.")
public_key_der = bytes.fromhex("302a300506032b6570032100") + public_key
public_key_base64 = base64.b64encode(public_key_der).decode("ascii")
with open(public_key_path, "w", encoding="ascii", newline="\n") as public_key_file:
    public_key_file.write("-----BEGIN PUBLIC KEY-----\n")
    for offset in range(0, len(public_key_base64), 64):
        public_key_file.write(public_key_base64[offset : offset + 64] + "\n")
    public_key_file.write("-----END PUBLIC KEY-----\n")
with open(signature_path, "rb") as signature_file:
    signature = base64.b64decode(signature_file.read().strip(), validate=True)
if len(signature) != 64:
    raise SystemExit("SoAI release manifest signature has an invalid length.")
with open(signature_binary_path, "wb") as signature_binary_file:
    signature_binary_file.write(signature)
PYTHON
    if ! soai_install_ui__capture "Release manifest signature verification" openssl pkeyutl \
        -verify \
        -pubin \
        -inkey "$public_key_path" \
        -rawin \
        -in "$SOAI_BOOTSTRAP_MANIFEST_PATH" \
        -sigfile "$signature_binary_path"; then
        soai_bootstrap__die "SoAI release manifest signature verification failed."
    fi
}

soai_bootstrap__validate_release() {
    soai_install_ui__capture "Release archive validation" python3 - \
        "$SOAI_BOOTSTRAP_MANIFEST_PATH" \
        "$SOAI_BOOTSTRAP_ARCHIVE_PATH" \
        "$SOAI_BOOTSTRAP_CHECKSUM_PATH" \
        "$SOAI_BOOTSTRAP_VERSION" \
        "$SOAI_BOOTSTRAP_RESOLVED_PLATFORM" \
        "$SOAI_BOOTSTRAP_MANIFEST_SIZE" \
        "$SOAI_BOOTSTRAP_SIGNATURE_SIZE" \
        "$SOAI_BOOTSTRAP_ARCHIVE_SIZE" \
        "$SOAI_BOOTSTRAP_CHECKSUM_SIZE" \
        "$SOAI_BOOTSTRAP_SIGNATURE_PATH" <<'PYTHON'
import hashlib
import json
import os
import re
import stat
import sys
import zipfile

(
    manifest_path,
    archive_path,
    checksum_path,
    version,
    platform,
    manifest_asset_size,
    signature_asset_size,
    archive_asset_size,
    checksum_asset_size,
    signature_path,
) = sys.argv[1:]
asset_sizes = (
    (manifest_path, int(manifest_asset_size)),
    (signature_path, int(signature_asset_size)),
    (archive_path, int(archive_asset_size)),
    (checksum_path, int(checksum_asset_size)),
)
for asset_path, expected_size in asset_sizes:
    if os.path.getsize(asset_path) != expected_size:
        raise SystemExit(f"Downloaded release asset size is invalid: {os.path.basename(asset_path)}")
with open(manifest_path, "r", encoding="utf-8") as manifest_file:
    manifest = json.load(manifest_file)
if not isinstance(manifest, dict):
    raise SystemExit("Signed SoAI release manifest is invalid.")
expected_scalars = {
    "schema_version": 1,
    "product": "SoAI",
    "edition": "soai-core",
    "version": version,
    "core_version": version,
    "signature_algorithm": "ed25519",
}
for field, expected_value in expected_scalars.items():
    if manifest.get(field) != expected_value:
        raise SystemExit(f"Signed SoAI release manifest field is invalid: {field}")
public_trust = manifest.get("public_trust")
if not isinstance(public_trust, dict) or public_trust.get("release_signing_key_sha256") != "e0333589b1ca792397182cc3f843989c021a056c61e281f8456c1da4f479f2a7":
    raise SystemExit("Signed SoAI release manifest public trust is invalid.")
archive_name = f"SoAI-{version}-linux-complete.zip"
archives = manifest.get("update_archives")
if not isinstance(archives, list):
    raise SystemExit("Signed SoAI release archive list is invalid.")
matches = [record for record in archives if isinstance(record, dict) and record.get("name") == archive_name]
if len(matches) != 1:
    raise SystemExit("Signed SoAI release does not contain exactly one Linux archive.")
archive_record = matches[0]
if archive_record.get("type") != "complete_archive" or archive_record.get("archive_root") != "SoAI":
    raise SystemExit("Signed SoAI Linux archive identity is invalid.")
if archive_record.get("platforms") != ["linux-x64", "linux-arm64"] or platform not in archive_record["platforms"]:
    raise SystemExit("Signed SoAI Linux archive platform assignment is invalid.")
expected_archive_size = archive_record.get("size_bytes")
expected_archive_sha256 = archive_record.get("sha256")
if expected_archive_size != os.path.getsize(archive_path):
    raise SystemExit("SoAI archive size does not match the signed manifest.")
if not isinstance(expected_archive_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_archive_sha256) is None:
    raise SystemExit("Signed SoAI archive digest is invalid.")
archive_digest = hashlib.sha256()
with open(archive_path, "rb") as archive_file:
    while True:
        chunk = archive_file.read(1024 * 1024)
        if not chunk:
            break
        archive_digest.update(chunk)
if archive_digest.hexdigest() != expected_archive_sha256:
    raise SystemExit("SoAI archive digest does not match the signed manifest.")
with open(checksum_path, "r", encoding="utf-8", newline="") as checksum_file:
    checksum_text = checksum_file.read()
if checksum_text != f"{expected_archive_sha256}  {archive_name}\n":
    raise SystemExit("SoAI archive checksum sidecar is invalid.")
file_records = archive_record.get("files")
if not isinstance(file_records, list) or not file_records:
    raise SystemExit("Signed SoAI archive file inventory is invalid.")
expected_files = {}
expected_casefold_paths = set()
for record in file_records:
    if not isinstance(record, dict):
        raise SystemExit("Signed SoAI archive file record is invalid.")
    relative_path = record.get("path")
    size_bytes = record.get("size_bytes")
    sha256 = record.get("sha256")
    if not isinstance(relative_path, str) or "\\" in relative_path:
        raise SystemExit("Signed SoAI archive file path is invalid.")
    path_parts = relative_path.split("/")
    if any(part in {"", ".", ".."} for part in path_parts):
        raise SystemExit("Signed SoAI archive file path is unsafe.")
    if relative_path in expected_files or relative_path.casefold() in expected_casefold_paths:
        raise SystemExit("Signed SoAI archive file inventory contains a duplicate path.")
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
        raise SystemExit("Signed SoAI archive file size is invalid.")
    if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        raise SystemExit("Signed SoAI archive file digest is invalid.")
    expected_files[relative_path] = (size_bytes, sha256)
    expected_casefold_paths.add(relative_path.casefold())
actual_files = {}
actual_casefold_paths = set()
with zipfile.ZipFile(archive_path, "r") as archive:
    if len(archive.infolist()) > 25000:
        raise SystemExit("SoAI archive contains too many entries.")
    for archive_info in archive.infolist():
        archive_path_text = archive_info.filename
        if "\\" in archive_path_text:
            raise SystemExit("SoAI archive contains an unsafe path.")
        archive_parts = archive_path_text.rstrip("/").split("/")
        if any(part in {"", ".", ".."} for part in archive_parts) or archive_parts[0] != "SoAI":
            raise SystemExit("SoAI archive contains an unsafe path.")
        if archive_info.is_dir():
            continue
        if archive_info.flag_bits & 1:
            raise SystemExit("SoAI archive contains an encrypted file.")
        unix_mode = archive_info.external_attr >> 16
        if unix_mode and stat.S_IFMT(unix_mode) not in {0, stat.S_IFREG}:
            raise SystemExit("SoAI archive contains a non-regular file.")
        relative_path = "/".join(archive_parts[1:])
        if not relative_path or relative_path in actual_files or relative_path.casefold() in actual_casefold_paths:
            raise SystemExit("SoAI archive contains a duplicate file path.")
        digest = hashlib.sha256()
        with archive.open(archive_info, "r") as archive_file:
            while True:
                chunk = archive_file.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        actual_files[relative_path] = (archive_info.file_size, digest.hexdigest())
        actual_casefold_paths.add(relative_path.casefold())
if actual_files != expected_files:
    raise SystemExit("SoAI archive files do not match the signed manifest inventory.")
PYTHON
}

soai_bootstrap__install() {
    local installer_path=""
    if [ -n "$SOAI_BOOTSTRAP_LOCAL_ROOT" ]; then
        installer_path="$SOAI_BOOTSTRAP_LOCAL_ROOT/install_soai_from_release.sh"
        if [ -f "$SOAI_BOOTSTRAP_LOCAL_ROOT/backend/core/bootstrap/filename_digests.json" ] && [ -f "$SOAI_BOOTSTRAP_LOCAL_ROOT/install-soai-from-release.sh" ]; then
            installer_path="$SOAI_BOOTSTRAP_LOCAL_ROOT/install-soai-from-release.sh"
        fi
    else
        local extraction_path="$SOAI_BOOTSTRAP_TEMP_DIR/extracted"
        mkdir -p "$extraction_path"
        unzip -q "$SOAI_BOOTSTRAP_ARCHIVE_PATH" -d "$extraction_path"
        installer_path="$extraction_path/SoAI/install-soai-from-release.sh"
    fi
    if [ ! -f "$installer_path" ] || [ -L "$installer_path" ]; then
        soai_bootstrap__die "Verified SoAI archive does not contain a regular installer."
    fi
    if [ "$SOAI_BOOTSTRAP_AUTOSTART" = "1" ]; then
        soai_bootstrap__status "Installing SoAI with automatic startup enabled..."
        soai_install_ui__stop
        if [ "${#SOAI_BOOTSTRAP_ELEVATE[@]}" -eq 0 ]; then
            soai_install_ui__delegate bash "$installer_path" --fast
        else
            sudo -v || soai_bootstrap__die "Unable to refresh administrator privileges."
            soai_install_ui__delegate "${SOAI_BOOTSTRAP_ELEVATE[@]}" bash -c 'unset SOAI_INSTALL_DIAGNOSTICS_DIR SOAI_INSTALL_UI_CONTEXT; export SOAI_INSTALL_UI_HEADER=1 SOAI_INSTALL_UI_PARENT=1; exec bash "$@"' bash "$installer_path" --fast
        fi
        return
    fi
    soai_bootstrap__status "Installing SoAI without a systemd service..."
    soai_install_ui__stop
    if [ "${#SOAI_BOOTSTRAP_ELEVATE[@]}" -eq 0 ]; then
            soai_install_ui__delegate bash "$installer_path" --target /opt/soai
        else
            sudo -v || soai_bootstrap__die "Unable to refresh administrator privileges."
            soai_install_ui__delegate "${SOAI_BOOTSTRAP_ELEVATE[@]}" bash -c 'unset SOAI_INSTALL_DIAGNOSTICS_DIR SOAI_INSTALL_UI_CONTEXT; export SOAI_INSTALL_UI_HEADER=1 SOAI_INSTALL_UI_PARENT=1; exec bash "$@"' bash "$installer_path" --target /opt/soai
        fi
    soai_install_ui__message information "Start SoAI manually with: soai"
}

soai_bootstrap__main() {
    set -euo pipefail
    soai_install_ui__init || exit 1
    trap soai_bootstrap__cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    trap soai_bootstrap__cleanup EXIT
    if [ "$(uname -s 2>/dev/null || true)" != "Linux" ]; then
        soai_bootstrap__die "This installer supports Linux only."
    fi
    case "$(uname -m 2>/dev/null || true)" in
        x86_64|amd64) SOAI_BOOTSTRAP_PLATFORM="linux-x64" ;;
        aarch64|arm64) SOAI_BOOTSTRAP_PLATFORM="linux-arm64" ;;
        *) soai_bootstrap__die "Unsupported Linux architecture: $(uname -m 2>/dev/null || true)" ;;
    esac
    soai_bootstrap__ask_autostart
    soai_bootstrap__require_autostart_support
    soai_bootstrap__resolve_local_payload
    soai_bootstrap__prepare_elevation "$@"
    soai_bootstrap__install_prerequisites
    if [ -z "$SOAI_BOOTSTRAP_LOCAL_ROOT" ]; then
        SOAI_BOOTSTRAP_TEMP_DIR="$(mktemp -d)"
        soai_bootstrap__resolve_release
        soai_bootstrap__download_release
        SOAI_INSTALL_UI_DOWNLOAD_PATH=""
        SOAI_INSTALL_UI_DOWNLOAD_TOTAL=0
        soai_bootstrap__status "Verifying the signed SoAI release..."
        soai_bootstrap__verify_signature
        soai_bootstrap__validate_release
        soai_install_ui__message completed "Release downloaded and verified."
    fi
    soai_bootstrap__install_path_command
    soai_install_ui__stop
    export SOAI_INSTALL_UI_PARENT=1
    soai_bootstrap__install
    SOAI_BOOTSTRAP_COMMAND_CREATED=0
    if [ -n "$SOAI_BOOTSTRAP_LOCAL_ROOT" ]; then
        soai_install_ui__message completed "Local SoAI installation completed successfully."
    else
        soai_install_ui__message completed "SoAI ${SOAI_BOOTSTRAP_VERSION} installation completed successfully."
    fi
}

soai_bootstrap__main "$@"
