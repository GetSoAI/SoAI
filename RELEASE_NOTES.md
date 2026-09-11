# SoAI Release Notes

## 1.1.0

SoAI 1.1.0 expands installation and application updates across Linux, Windows, and macOS, redesigns the chat composer, and improves plugin management, streamed conversations, and recovery. All eight bundled plugins are included at version 1.0.1.

### Installation and updates

- The Core release set now contains the Linux x64/arm64 complete archive, the macOS Intel/Apple-silicon complete archive, the Windows x64 setup executable, and a Windows x64 complete archive containing the compiled native launcher. The primary V1 manifest retains its released Linux and Windows setup shape, while separately named signed macOS and Windows-archive V1 manifests authenticate the complete archives without changing the V1 automatic-update contract.
- The macOS network installer now resolves the published macOS archive, and the stable `https://soai.to/install/mac` command installs it on Intel or Apple silicon.
- The WebUI installs signed complete archives on Linux and macOS. On Windows it verifies the signed installer record, hands the setup executable to an external update process, and upgrades the existing installation in place.
- Windows setup now preserves application files for rollback before an upgrade. A failed installer restores the previous application files while retaining `data/`.
- The extracted Windows complete archive installs through `install-soai-from-release.bat`, supports an explicit target, preserves target data across repeated installation, and has a target-scoped uninstall path.
- Accepted update tasks retain their updater ownership through application shutdown. Startup checks task consistency before committing activation, so shutdown cannot incorrectly cancel an update that is still running.
- Unsupported platforms can still check release availability, but the WebUI disables installation instead of starting a path that cannot succeed.
- Archive updates preserve custom plugin packages, configuration sidecars, compatible newer installed packages, and unrelated files at the installation root. Package identity conflicts, differing bytes at the same package version, and incompatible installed packages stop the update before file replacement.
- Rollback retains original copies across repeated restoration attempts and restores bundled defaults and vendor files to their original data paths. Interrupted cleanup does not repeat a completed rollback.
- An interrupted update is no longer reported as completed solely because the installed version matches its target.
- Update completion requires successful startup and activation of the updated application. Failed activation can restore application files and update-managed database and configuration state.
- Update preflight rejects unsupported newer database schemas before replacing files. Archive update hooks and direct application restarts retain the explicitly selected configuration path.
- Runtime HTTP requests honor proxy environment variables when `MODELS.ROUTING.HTTP_CLIENT_TRUST_ENV` is enabled, including `NO_PROXY` bypasses. Destination restrictions remain enforced, and offline mode rejects proxy routes.
- The WebUI allows update preparation to finish within its supported deadline instead of aborting the request after 30 seconds.
- Leaving the Updates page while its confirmation is pending prevents a late confirmation from starting installation.
- The update refresh button stays hidden while installation is pending, so a new check cannot replace installation progress.
- Windows installation retries reuse downloaded Python packages, avoiding unnecessary repeat downloads.
- Windows installation recognizes active runtime-file downloads, avoiding false inactivity failures during large downloads.
- Windows stops failed update preparation without a secondary process-cleanup error, while preserving process-identity checks.
- Windows setup accepts an already-stopped application after verifying that no instance is running. Failed update handoffs retain diagnostic details for the installer and recovery operations.
- Windows uninstall preserves the installation when update recovery or cleanup is pending. Reopen SoAI to complete recovery before retrying uninstall.
- Update downloads batch disk reservations to avoid excessive disk writes on fragmented connections. Failed transfers close and remove their temporary files, including after cancellation or invalid download sizes.
- Windows setup preserves existing application data when installation registration is missing or points elsewhere. If the existing file inventory cannot be read, setup stops before replacing files. Unrecognized installation folders must be empty.
- Windows updates correctly recognize valid preparation folders and reject unreadable or nonempty preparation folders before replacing application files.
- Windows rollback validates retained recovery metadata before removing installed files. Missing or corrupt backup metadata stops restoration and retains the files for repair.
- Windows upgrade backups support long runtime paths. Application restoration preserves Windows file and directory access permissions, including restricted files and explicit access denials.

### Chat and assistant tools

- Added offline search and page reading for the documentation bundled with the installed release. Authorized conversation users can also use the stop tool without administrator access; both tools remain unavailable through MCP server mode.
- Redesigned chat composer and model controls make conversation setup and model selection easier to manage.
- Chat presets can enable the new-conversation input action, including a new-conversation action on mobile.
- Added an optional Ctrl/Cmd + Enter to send preference. When enabled, Enter inserts a newline. The default remains Enter to send, and Ctrl/Cmd + Enter sends in either mode.
- Fixed competing draft saves, message-edit completion, and resubmission of persisted messages.
- Stream finalization persists the final visible text and activity history before announcing completion. Repeated finalization attempts do not duplicate the committed result.
- Failed or cancelled generation retains partial response text. Image-only and thinking-only responses are handled during finalization.
- Fixed delayed tool-status updates, tool-source attribution, and processing indicators that remained active after the associated activity finished.
- Improved ordering and freshness of streamed text, thinking activity, and tool events.
- Restricting or disabling external MCP server exposure no longer unintentionally reduces the tool catalog available inside SoAI or through its local OpenAI-compatible tool bridge. External exposure restrictions remain enforced.

### Plugin and model management

- Plugin cards show progress tracks, percentages, and operation labels, with action availability and cancellation controls that follow the active operation.
- Failed or cancelled plugin uploads clean up partial registration and upload placeholders. Valid but incompatible packages remain visible in a disabled state with a compatibility explanation.
- Improved localized compatibility messages, installed backend-variant display, and provider-dialog initialization after catalog loading.
- Fixed provider counts on the Models page and improved model-download background activity tracking.
- Improved plugin visibility during startup and added display of logos from verified plugin packages.

### Hardware and reliability

- NVIDIA capability discovery uses bounded compute waits, inventory gating, and probe-progress tracking.
- Improved NVIDIA display-environment discovery and protection against stale capability results. GPU-vendor failures are reflected in the affected vendor's state.
- Improved GPU hardware-card loading and resource-recovery presentation, and fixed numeric interpretation of SoAIBench score confidence.
- Delayed Guardian recovery attempts check whether the plugin's state has changed before acting. Guardian no longer starts recovery during application shutdown.
- Fixed models remaining in a pending-dispatch state when no eligible waiting request remained after loading.
- Improved startup readiness, restart handoff, and shutdown handling, including active HTTP responses and background-task cleanup.
- Unexpected WebSocket snapshot failures are contained at the request boundary. Routine WebSocket, tool-result, and database-cleanup logging is less noisy.
- Database vacuum handling prevents maintenance outages from disrupting normal database use.
- Improved vacuum cancellation, deferral, retry scheduling, startup eligibility, and maintenance-status reporting. Busy database checkpoints use backoff so normal database work can continue.
- Fixed a WebUI startup failure caused by database-maintenance status in the server’s health response.

### Files and interface

- Log timestamps now identify UTC explicitly in text output and the WebUI, and daily log rotation follows UTC day boundaries.
- Improved image-preview paging, cursor-centered zoom, dragging, and touch gestures, including inertial movement and downward dismissal. Adjacent-image caching reduces repeat loading while browsing.
- Improved image-viewer keyboard access and reduced-motion behavior.
- Fixed Windows host-folder selection and discovery when drives are unavailable.
- Fixed narrow-screen chat status layout, page-scrollbar overlap with the header, file-row presentation, and loading-state transitions.
- Fixed header-clock visibility when disabled and improved the automation calendar's day view.
- Scheduling a one-time automation with a start time in the past now produces a localized, actionable error.

### Website and documentation

- The SoAI website brings installation entrypoints and documentation together, covering setup, model management, assistant tools, administration, and updates.
- Added a public Plugin Store for browsing and downloading bundled plugins, along with an interactive explanation of request orchestration and a screenshot gallery.
- Expanded searchable documentation for configuration, access control, hardware, assistant tools, installation, and recovery, with downloadable text versions.
- Improved mobile navigation and documentation browsing.

### Compatibility and upgrade checks

- SoAI 1.1.0 establishes the supported compatibility baseline for subsequent releases. Earlier releases are outside the supported upgrade baseline; the plugin minimum-version declarations below do not establish an application upgrade guarantee.
- Before updating an existing installation, create and download a backup through Settings > Backup and confirm that the target release supports the installed edition, platform, and source version. Core packages cannot update a SoAI OS installation.
- After updating, confirm the displayed version and check authentication, plugin health, model availability, files, automations, and the workflows you use. If recovery remains pending, follow the recovery guidance in the documentation at [SoAI](https://soai.to) rather than manually editing application data.

### Platform support and verification

- Windows remains x64-only. Windows ARM64 has no installer or automatic update path.
- macOS does not expose SoAI GPU telemetry or tuning; compatible local backends may continue to use their own Metal support.
- Windows executables are currently unsigned. Verify the signed SoAI release manifest and artifact checksum before approving any operating-system warning.

### Release verification

- Signed Ed25519 manifests bind artifact names, platform assignments, sizes, SHA-256 digests, archive roots, and the files in each complete archive. Automatic updates reject missing, invalid, ambiguous, unsigned, unsupported, incomplete, or tampered assets.
- Use the offline release verifier and compare the raw Ed25519 public-key SHA-256 fingerprint with the trusted value in `SECURITY.md`. A checksum without an authenticated manifest is insufficient.
- Repository-generated source snapshots contain source; install from the complete archives or platform installer.
- Release artifacts include built frontend assets, production backend files and plugins, platform-specific launch and installation entrypoints, legal notices, security policy, documentation, and release notes.

### Bundled plugins

SoAI includes External, Ollama, vLLM, llama.cpp, cTranslate2, Embedding, Whisper, and MeloTTS. Each plugin's metadata defines its provisioning requirements and hardware restrictions.

- All eight packages are version 1.0.1 and include packaged logo assets, with refreshed External branding. Their declared minimum compatibility versions are unchanged.
- Ollama keeps process tracking responsive during startup and HTTP readiness checks. Concurrent starts wait for the active attempt, and failed or cancelled starts clean up only the process owned by that attempt. Listener-identity checks run off the event loop.
- Ollama streaming reports the `tool_calls` finish reason when tool calls appeared before the final response chunk.
- The other seven packages contain logo and version-metadata changes; their inference implementations are unchanged from the preceding bundled packages.
