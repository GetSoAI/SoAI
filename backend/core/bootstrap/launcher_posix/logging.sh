#!/usr/bin/env bash
# SoAI - POSIX launcher console logging primitives [backend/core/bootstrap/launcher_posix/logging.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

SOAI_LAUNCHER_COLOR_RESET=$'\033[0m'
SOAI_LAUNCHER_COLOR_INFO=$'\033[92m'
SOAI_LAUNCHER_COLOR_WARN=$'\033[0;33m'
SOAI_LAUNCHER_COLOR_TAG=$'\033[38;5;215m'
SOAI_LAUNCHER_COLOR_SEP=$'\033[38;5;246m'

soai_managed_runtime__die() {
    echo "ERROR: $1" >&2
    return 1
}

soai_launcher__info() {
    printf "%s%s%s %s-%s %s[SoAI/Linux_Launcher]%s %s-%s %sINFO%s %s-%s %s\n" \
        "$SOAI_LAUNCHER_COLOR_SEP" \
        "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$SOAI_LAUNCHER_COLOR_SEP" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$SOAI_LAUNCHER_COLOR_TAG" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$SOAI_LAUNCHER_COLOR_SEP" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$SOAI_LAUNCHER_COLOR_INFO" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$SOAI_LAUNCHER_COLOR_SEP" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$1"
}

soai_launcher__warn() {
    printf "%s%s%s %s-%s %s[SoAI/Linux_Launcher]%s %s-%s %sWARN%s %s-%s %s\n" \
        "$SOAI_LAUNCHER_COLOR_SEP" \
        "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$SOAI_LAUNCHER_COLOR_SEP" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$SOAI_LAUNCHER_COLOR_TAG" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$SOAI_LAUNCHER_COLOR_SEP" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$SOAI_LAUNCHER_COLOR_WARN" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$SOAI_LAUNCHER_COLOR_SEP" \
        "$SOAI_LAUNCHER_COLOR_RESET" \
        "$1" >&2
}
