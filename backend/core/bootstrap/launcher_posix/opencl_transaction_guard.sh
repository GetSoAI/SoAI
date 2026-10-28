#!/usr/bin/env bash
# SoAI - POSIX launcher OpenCL APT transaction commit guard [backend/core/bootstrap/launcher_posix/opencl_transaction_guard.sh]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

set -euo pipefail

if [ "$#" -ne 1 ] || [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "SoAI OpenCL transaction guard: the admitted transaction record is unavailable." >&2
    exit 1
fi

awk -v admitted_path="$1" '
    function reject(message) {
        rejection = message
        exit 1
    }
    BEGIN {
        while ((read_status = (getline admitted_line < admitted_path)) > 0) {
            if (split(admitted_line, admitted_field, " ") != 3) {
                reject("the admitted transaction record is malformed")
            }
            admitted_key = admitted_field[1] SUBSEP admitted_field[2] SUBSEP admitted_field[3]
            if (admitted_key in unpacked) reject("the admitted transaction record is malformed")
            unpacked[admitted_key] = 0
            admitted_count++
        }
        close(admitted_path)
        if (read_status < 0 || admitted_count == 0) {
            reject("the admitted transaction record is unavailable")
        }
    }
    NR == 1 {
        if ($0 != "VERSION 3") reject("APT supplied unsupported hook protocol: " substr($0, 1, 40))
        next
    }
    !configuration_complete {
        if ($0 == "") configuration_complete = 1
        next
    }
    {
        if (NF != 9) reject("APT supplied a malformed or unsupported package action")
        if ($2 != "-" || $3 != "-" || $4 != "none") reject("APT would change installed package " $1)
        if ($5 != "<" || $8 !~ /^(same|foreign|allowed|none)$/) {
            reject("APT supplied a malformed or unsupported package action")
        }
        action_key = $1 SUBSEP $7 SUBSEP $6
        if (!(action_key in unpacked)) reject("APT would install unadmitted package " $1 " " $6 " " $7)
        if ($9 == "**CONFIGURE**") next
        if ($9 !~ /^\/.+\.deb$/) reject("APT supplied an unsupported action for package " $1)
        if (unpacked[action_key]++ != 0) reject("APT supplied duplicate package " $1)
    }
    END {
        if (rejection == "" && !configuration_complete) rejection = "APT supplied incomplete transaction evidence"
        if (rejection == "") {
            for (admitted_key in unpacked) {
                if (unpacked[admitted_key] != 1) rejection = "APT omitted part of the admitted transaction"
            }
        }
        if (rejection != "") {
            print "SoAI OpenCL transaction guard: " rejection "; dpkg was not started." > "/dev/stderr"
            exit 1
        }
    }
'
