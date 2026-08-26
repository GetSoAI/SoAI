#!/usr/bin/env bash

soai_bootstrap__status() {
    printf ">>> %s\n" "$*" >&2
}

soai_bootstrap__die() {
    printf "ERROR: %s\n" "$*" >&2
    exit 1
}

soai_bootstrap__cleanup() {
    if [ "${SOAI_BOOTSTRAP_COMMAND_CREATED:-0}" = "1" ] \
        && [ -L "${SOAI_BOOTSTRAP_COMMAND_PATH:-}" ] \
        && [ "$(readlink "$SOAI_BOOTSTRAP_COMMAND_PATH")" = "${SOAI_BOOTSTRAP_COMMAND_TARGET:-}" ]; then
        "${SOAI_BOOTSTRAP_ELEVATE[@]}" rm -f -- "$SOAI_BOOTSTRAP_COMMAND_PATH" || \
            soai_bootstrap__status "Failed to roll back the SoAI command: ${SOAI_BOOTSTRAP_COMMAND_PATH}"
    fi
    if [ -n "${SOAI_BOOTSTRAP_TEMP_DIR:-}" ] && [ -d "$SOAI_BOOTSTRAP_TEMP_DIR" ]; then
        rm -rf -- "$SOAI_BOOTSTRAP_TEMP_DIR"
    fi
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
        soai_bootstrap__status "No interactive terminal is available; automatic startup is disabled."
        return
    fi
    local response=""
    if read -r -t 30 -p "Start SoAI automatically at system startup? [y/N] " response < /dev/tty; then
        case "$response" in
            y|Y|yes|YES|Yes) SOAI_BOOTSTRAP_AUTOSTART=1 ;;
            n|N|no|NO|No|"") ;;
            *) soai_bootstrap__status "Unrecognized response; automatic startup is disabled." ;;
        esac
    else
        printf "\n" > /dev/tty 2>/dev/null || true
        soai_bootstrap__status "No response received within 30 seconds; automatic startup is disabled."
    fi
}

soai_bootstrap__prepare_elevation() {
    SOAI_BOOTSTRAP_ELEVATE=()
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        return
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        soai_bootstrap__die "SoAI requires root privileges for installation, but sudo is unavailable."
    fi
    soai_bootstrap__status "Root privileges are required to install SoAI in /opt/soai."
    sudo -v || soai_bootstrap__die "Unable to obtain root privileges through sudo."
    SOAI_BOOTSTRAP_ELEVATE=(sudo)
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
            soai_bootstrap__status "SoAI command is already installed: ${SOAI_BOOTSTRAP_COMMAND_PATH}"
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
    soai_bootstrap__status "Installed SoAI command: ${SOAI_BOOTSTRAP_COMMAND_PATH}"
}

soai_bootstrap__resolve_local_payload() {
    SOAI_BOOTSTRAP_LOCAL_ROOT=""
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
    SOAI_BOOTSTRAP_LOCAL_ROOT="$source_root"
    soai_bootstrap__status "Complete local SoAI payload detected; release download will be skipped."
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
    "${SOAI_BOOTSTRAP_ELEVATE[@]}" env DEBIAN_FRONTEND=noninteractive apt-get update
    "${SOAI_BOOTSTRAP_ELEVATE[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install \
        -y --no-install-recommends "${required_packages[@]}"
}

soai_bootstrap__download() {
    local url="$1"
    local destination="$2"
    local maximum_bytes="$3"
    local timeout_seconds="$4"
    curl \
        --fail \
        --show-error \
        --location \
        --proto '=https' \
        --tlsv1.2 \
        --connect-timeout 15 \
        --max-time "$timeout_seconds" \
        --max-filesize "$maximum_bytes" \
        --retry 3 \
        --retry-delay 2 \
        --output "$destination" \
        "$url"
    if [ ! -s "$destination" ]; then
        soai_bootstrap__die "Downloaded asset is empty: ${url}"
    fi
}

soai_bootstrap__resolve_release() {
    local release_json="$SOAI_BOOTSTRAP_TEMP_DIR/release.json"
    local metadata_path="$SOAI_BOOTSTRAP_TEMP_DIR/release-metadata.tsv"
    soai_bootstrap__status "Resolving the latest published SoAI release from GitHub..."
    curl \
        --fail \
        --show-error \
        --location \
        --proto '=https' \
        --tlsv1.2 \
        --connect-timeout 15 \
        --max-time 120 \
        --max-filesize 8388608 \
        --retry 3 \
        --retry-delay 2 \
        --header 'Accept: application/vnd.github+json' \
        --header 'X-GitHub-Api-Version: 2022-11-28' \
        --user-agent 'SoAI-Installer/1' \
        --output "$release_json" \
        'https://api.github.com/repos/GetSoAI/SoAI/releases/latest'
    python3 - "$release_json" "$metadata_path" "$SOAI_BOOTSTRAP_PLATFORM" <<'PYTHON'
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
    soai_bootstrap__download "$SOAI_BOOTSTRAP_ARCHIVE_URL" "$SOAI_BOOTSTRAP_ARCHIVE_PATH" 2147483648 7200
}

soai_bootstrap__verify_signature() {
    local public_key_path="$SOAI_BOOTSTRAP_TEMP_DIR/release-public-key.pem"
    local signature_binary_path="$SOAI_BOOTSTRAP_TEMP_DIR/manifest-signature.bin"
    python3 - "$public_key_path" "$SOAI_BOOTSTRAP_SIGNATURE_PATH" "$signature_binary_path" <<'PYTHON'
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
    if ! openssl pkeyutl \
        -verify \
        -pubin \
        -inkey "$public_key_path" \
        -rawin \
        -in "$SOAI_BOOTSTRAP_MANIFEST_PATH" \
        -sigfile "$signature_binary_path" >/dev/null 2>&1; then
        soai_bootstrap__die "SoAI release manifest signature verification failed."
    fi
}

soai_bootstrap__validate_release() {
    python3 - \
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
        installer_path="$SOAI_BOOTSTRAP_LOCAL_ROOT/install-soai-from-release.sh"
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
        "${SOAI_BOOTSTRAP_ELEVATE[@]}" bash "$installer_path" --fast
        return
    fi
    soai_bootstrap__status "Installing SoAI without a systemd service..."
    "${SOAI_BOOTSTRAP_ELEVATE[@]}" bash "$installer_path" --target /opt/soai
    soai_bootstrap__status "Start SoAI manually with: soai"
}

soai_bootstrap__main() {
    set -euo pipefail
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
    soai_bootstrap__prepare_elevation
    soai_bootstrap__install_prerequisites
    if [ -z "$SOAI_BOOTSTRAP_LOCAL_ROOT" ]; then
        SOAI_BOOTSTRAP_TEMP_DIR="$(mktemp -d)"
        soai_bootstrap__resolve_release
        soai_bootstrap__download_release
        soai_bootstrap__status "Verifying the signed SoAI release..."
        soai_bootstrap__verify_signature
        soai_bootstrap__validate_release
    fi
    soai_bootstrap__install_path_command
    soai_bootstrap__install
    SOAI_BOOTSTRAP_COMMAND_CREATED=0
    if [ -n "$SOAI_BOOTSTRAP_LOCAL_ROOT" ]; then
        soai_bootstrap__status "Local SoAI installation completed successfully."
    else
        soai_bootstrap__status "SoAI ${SOAI_BOOTSTRAP_VERSION} installation completed successfully."
    fi
}

soai_bootstrap__main "$@"
