#!/usr/bin/env bash

soai_macos_install__status() {
    printf ">>> %s\n" "$*" >&2
}

soai_macos_install__die() {
    printf "ERROR: %s\n" "$*" >&2
    exit 1
}

soai_macos_install__cleanup() {
    if [ -n "${SOAI_MACOS_INSTALL_TEMP_DIR:-}" ] && [ -d "$SOAI_MACOS_INSTALL_TEMP_DIR" ]; then
        rm -rf -- "$SOAI_MACOS_INSTALL_TEMP_DIR"
    fi
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
        soai_macos_install__status "No interactive terminal is available; automatic startup is disabled."
        return
    fi
    local response=""
    if read -r -t 30 -p "Start SoAI automatically at system startup? [y/N] " response < /dev/tty; then
        case "$response" in
            y|Y|yes|YES|Yes) SOAI_MACOS_INSTALL_AUTOSTART=1 ;;
            n|N|no|NO|No|"") ;;
            *) soai_macos_install__status "Unrecognized response; automatic startup is disabled." ;;
        esac
    else
        printf "\n" > /dev/tty 2>/dev/null || true
        soai_macos_install__status "No response received within 30 seconds; automatic startup is disabled."
    fi
}

soai_macos_install__prepare_elevation() {
    SOAI_MACOS_INSTALL_ELEVATE=()
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        return
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        soai_macos_install__die "SoAI requires administrator privileges for installation, but sudo is unavailable."
    fi
    soai_macos_install__status "Administrator privileges are required to install SoAI in /Applications/SoAI."
    sudo -v || soai_macos_install__die "Unable to obtain administrator privileges through sudo."
    SOAI_MACOS_INSTALL_ELEVATE=(sudo)
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
    soai_macos_install__status "Complete local SoAI payload detected; release download will be skipped."
}

soai_macos_install__download() {
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
        soai_macos_install__die "Downloaded asset is empty: ${url}"
    fi
}

soai_macos_install__resolve_release() {
    local release_json="$SOAI_MACOS_INSTALL_TEMP_DIR/release.json"
    local metadata_path="$SOAI_MACOS_INSTALL_TEMP_DIR/release-metadata.tsv"
    local resolver_path="$SOAI_MACOS_INSTALL_TEMP_DIR/resolve-release.js"
    soai_macos_install__status "Resolving the latest published SoAI release from GitHub..."
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
    osascript -l JavaScript "$resolver_path" "$release_json" > "$metadata_path"
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
    soai_macos_install__download "$SOAI_MACOS_INSTALL_ARCHIVE_URL" "$SOAI_MACOS_INSTALL_ARCHIVE_PATH" 2147483648 7200
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
    actual_hash="$(shasum -a 256 "$SOAI_MACOS_INSTALL_ARCHIVE_PATH" | awk '{print $1}')"
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
        unzip -q "$SOAI_MACOS_INSTALL_ARCHIVE_PATH" -d "$extraction_path"
        installer_path="$extraction_path/SoAI/install-soai-from-release.sh"
    fi
    if [ ! -f "$installer_path" ] || [ -L "$installer_path" ]; then
        soai_macos_install__die "SoAI payload does not contain a regular installer."
    fi
    if [ "$SOAI_MACOS_INSTALL_AUTOSTART" = "1" ]; then
        soai_macos_install__status "Installing SoAI with launchd automatic startup enabled..."
        "${SOAI_MACOS_INSTALL_ELEVATE[@]}" bash "$installer_path" --fast
        return
    fi
    soai_macos_install__status "Installing SoAI without a launchd service..."
    "${SOAI_MACOS_INSTALL_ELEVATE[@]}" bash "$installer_path" --target /Applications/SoAI
    soai_macos_install__status "Start SoAI manually with: sudo /Applications/SoAI/soai.command"
}

soai_macos_install__main() {
    set -euo pipefail
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
        soai_macos_install__status "Verifying the SoAI release checksum..."
        soai_macos_install__validate_release
    fi
    soai_macos_install__install
    if [ -n "$SOAI_MACOS_INSTALL_LOCAL_ROOT" ]; then
        soai_macos_install__status "Local SoAI installation completed successfully."
    else
        soai_macos_install__status "SoAI ${SOAI_MACOS_INSTALL_VERSION} installation completed successfully."
    fi
}

soai_macos_install__main "$@"
