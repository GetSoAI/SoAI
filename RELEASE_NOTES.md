# SoAI Release Notes

## 1.0.0 — 22 August 2026

SoAI 1.0.0 is the first source-available release. No compatibility with earlier development snapshots is promised.

### Release and update contract

- `SoAI-1.0.0-linux-complete.zip` is the runnable Linux x64/arm64 product and automatic-update payload.
- `SoAI-1.0.0-windows-x64-setup.exe` is the Windows x64 installer.
- `SoAI-1.0.0-release-manifest-v1.json`, its `.sig`, and exact per-artifact `.sha256` sidecars authenticate the release set.
- GitHub-generated source ZIP/TAR snapshots contain source and are not runnable products or update payloads.
- `SoAI-Connect-1.0.0-<timestamp>.apk` is the sideloaded Android companion client, published with a `.sha256` sidecar in the separate SoAI Connect repository and outside the Core signed manifest.
- Linux x64 and Linux arm64 are the automatic-update platform matrix. Windows updates use the installer; macOS packaging remains untested and unpublished.
- A signed Ed25519 V1 manifest binds artifact names, platform assignments, sizes, SHA-256 digests, archive roots, and every regular file in each complete archive.
- Automatic updates fail closed for missing, invalid, ambiguous, unsigned, unsupported, incomplete, or tampered release assets.
- Release artifacts contain only built frontend assets, production backend files and plugins, platform-specific launch and installation entrypoints, legal notices, security policy, documentation, and these release notes.

### SoAI Connect for Android

`SoAI-Connect-1.0.0-<timestamp>.apk` is the companion Android client for Android 8.0 (API 26) and newer. It is a hardened shell around a SoAI server's own web interface: it discovers the server on the local network, pins the server certificate on first trust, and forwards SoAI WebUI notifications to the Android notification shade over a direct connection that does not depend on Google Play services.

- The APK is a companion artifact with its own `.sha256` sidecar. It is not covered by the signed V1 manifest and is never an automatic-update input.
- Distribution is by sideloading from <https://github.com/GetSoAI/SoAI_Connect/releases>; there is no app-store listing. The client source is published in that same separate repository.
- The package is signed with APK Signature Scheme v2 and v3 and carries no v1 JAR signature.
- The separate SoAI Connect repository records every component embedded in the package and reproduces that notice inside the app under About.

### Bundled plugins

The initial release bundles External, Ollama, vLLM, llama.cpp, cTranslate2, Embedding, Whisper, and MeloTTS. Plugin-specific provisioning and hardware restrictions remain defined by each plugin's metadata.

### Verification

Compare the raw Ed25519 public-key SHA-256 fingerprint with the trusted value in `SECURITY.md`, then use the published offline release verifier from a trusted SoAI source checkout. The verifier authenticates the signed manifest and validates exact sidecars, artifact hashes, required platform payloads, frontend bundles, and every signed archive file record. A checksum without the authenticated manifest is insufficient.

### Known release constraints

- The Windows x64 archive and installer must be produced on Windows from the internal Windows build kit before release finalization.
- The production signing private key and password are external release secrets and are never included in source or release archives.
- SoAI remains V1-only until after its first public release.

This file is the canonical release-body source for the 1.0.0 GitHub release.
