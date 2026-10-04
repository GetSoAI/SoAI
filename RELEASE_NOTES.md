# SoAI Release Notes

## 1.3.1

SoAI 1.3.1 fixes Windows installations, lets Linux installations obtain root access on systems where sudo is missing or not permitted, and makes the Linux and macOS installers easier to follow when something goes wrong. It also fixes problems in Chat, the setup wizard, provider and model settings, and startup after a clock change.

### Highlights

- Windows setup and the Windows complete archive now check the Microsoft Visual C++ runtime before preparing SoAI. When the runtime on the computer is older than version 14.44, which SoAI's AI libraries require, SoAI installs or repairs it from Microsoft and places the required runtime files in its own Python folders, so an older copy elsewhere on the system is no longer loaded instead. On affected computers, installation previously failed with a DLL initialization error (WinError 1114).
- On Linux, the network installer, `install-soai-from-release.sh --fast`, the `soai` command for installations owned by root, and the uninstaller no longer stop when sudo is unavailable. SoAI uses sudo when it is permitted, then `sudo su` when only that is allowed, then `su` with the root password (3 attempts, and Ctrl+C cancels). If none of these work, it stops with a message naming each method it tried.
- The Linux and macOS installers show the current step on one progress line with the elapsed time and, for downloads, the percentage completed, while the full output of every command is kept in a private diagnostic folder. When a step fails, the installer shows the check that failed, its exit code, an excerpt of the error, the location of the full log, and a command you can run to read it.

### Improvements

- The File Explorer header has a Change folder button that opens Settings > Users, where you change your account's default folder. In narrow windows it moves into the page actions menu with the other header buttons.
- You can add an external provider without an API key, in both the add-provider window and the setup wizard, for providers that do not require one.
- When no theme has been saved yet, the WebUI and the setup wizard start in the operating system's light or dark theme instead of starting dark and switching after the administrator account is created.

### Fixes

- If the computer's clock moved back after someone signed in, SoAI no longer fails to start or reinstall with "System clock precedes active WebUI session chronology." Sign-ins recorded at the later time end, and those users sign in again.
- Live token speed in Chat, on the Dashboard, and in Metrics history no longer stalls when a response contains a `<` character that does not start a tag, such as a comparison like `a < b`. The Chat token counter also keeps following a response that is still streaming when you change the selected model or return to its conversation.
- A Retry row for a regenerated response no longer appears when the regeneration cannot be retried or while other conversation inputs are still active.
- Activity rows in Chat expand as soon as you click them, even while their tool images are still loading. Restoring a minimized window during a response no longer briefly shows placeholder previews, and the main status no longer switches to reconnecting while a routine status refresh is in progress.
- In the setup wizard, the create account button stays in its loading state until the next step appears, so a slow computer cannot submit the account twice. An account error now opens and closes smoothly, and the AI sources step shows a single Skip SoAI setup button.
- On a model's OpenAI capabilities, a capability the model does not support is shown as locked with an explanation instead of turning on and immediately back off.
- The folder picker and the plugin clone controls use the standard spacing and separators.

## 1.3.0

SoAI 1.3.0 adds a guided setup that gets a first model running, push-to-talk and a sketch pad in Chat, right-to-left layouts for Arabic and Persian, QR pairing for the SoAI Connect app, and built-in wallpapers. It also lowers idle CPU use, makes downloads and in-app updates more dependable, and moves the llama.cpp and embedding plugins to llama.cpp v0.5.0.

### Highlights

- First-run setup now continues after account creation and helps you get a model working. You choose whether models run on this device, through a cloud provider, or both, and SoAI can install a suitable local engine, suggest models that fit your hardware with their download size and expected speed, connect a provider from its API URL and key, and send a short test message before opening Chat. Downloads and installations keep running in the background if you move on early, and a Finish SoAI setup link brings you back to any step that still needs attention.
- Chat supports push-to-talk. Hold the microphone button to record, release it to send, or slide left to cancel. SoAI transcribes the recording and sends it, unless the draft or the selected model changed while it was transcribing, in which case the transcript stays in the composer for you to review. Holding the token counter opens Parameters at the context length setting, and holding the configuration or Tools button opens Presets or Tools settings.
- Chat can show a Sketch input action, which you turn on under Chat configuration > Appearance > Input actions. Draw with a mouse, pen, or finger using brushes, shapes, colors, and undo/redo, then attach the drawing as an image. Vision models receive the image, and other models can use the existing OCR path.
- Arabic and Persian now use a mirrored right-to-left layout throughout the WebUI, while code, file paths, and logs stay left-to-right.
- Settings > Connect shows a QR code and the reachable server addresses for pairing the SoAI Connect Android app, version 1.0.3 or later, so you no longer need to type the server address. The phone must be able to reach the chosen address on the same network or through a VPN.
- The WebUI uses less CPU while idle. With all Dashboard widgets enabled, idle CPU use on the Dashboard is about 55% lower than in 1.2.1, and about 30 to 35% lower on the Metrics and Hardware pages. Pages also render faster on a cold load, and the server spends less time scanning plugin worker processes, which could delay realtime updates on busy systems.

### Improvements

- The empty chat composer and the conversation header can fold away while you read earlier messages. Both settings are under Chat configuration > Appearance and are enabled by default. The composer returns when you scroll down, type, or need to answer an assistant prompt, and a running response keeps its Stop button visible.
- Opening Chat without choosing a conversation reopens the one you last had open, at the same scroll position, or the most recent conversation if that one no longer exists.
- When the Chat sidebar is collapsed, resting the mouse on its toggle button opens it over the conversation without resizing the page, and it closes again shortly after the pointer leaves. The main WebUI navigation sidebar opens the same way from its menu button.
- In Plan mode, the assistant's system prompt now has models deliver the finished plan through the plan tool with only a brief summary in chat, so the plan appears in the conversation's plan view where you can review and approve it. Models no longer offer to carry out the plan themselves and instead ask you to switch to Execute mode.
- Context compaction first asks the model for its summary with reasoning turned off, so thinking models compact conversations faster. If that attempt fails or returns nothing, SoAI retries once with the model's normal reasoning.
- Collapsed subagent activity shows the latest live child activity during longer runs. Activity details no longer repeat the subagent's final text, and streamed tool activity follows the order in which it was produced.
- The model detail page has been redesigned. Parameters are grouped in a category rail that can also show only customized settings or unsaved changes, each unsaved change can be reverted on its own, and backend defaults appear as placeholders. The Overview tab shows status in its own column next to the model details, inference defaults, and capabilities.
- The Automation editor shows when an automation will next run, in its time zone and in yours, and explains when a clock change moves or repeats a scheduled time. It checks that the selected model is installed, enabled, and supports chat before saving, and warns when the automation was changed elsewhere while you were editing it, letting you keep your changes or load the latest version. Skipping, stopping, or removing an occurrence now asks for confirmation, the calendar and side pane can be resized, and the page marks its data as out of date when it cannot refresh.
- On the Hardware page, SoAIBench can ask which GPU to benchmark when several are available, and a runs panel makes completed runs easier to find. Benchmarks keep running when you close their window, which shows every run from the current visit with its own progress and report. When the same GPU appears on several OpenCL platforms, SoAIBench prefers the vendor's own platform, and score sharing shows a clearer confirmation with a link to the published result.
- Metrics can chart historical effective token throughput. Metrics and Hardware history charts load older samples as you pan and zoom, switch to a finer or coarser resolution as you zoom, keep the visible time range steady while earlier data arrives, and label periods when SoAI was offline.
- Resetting Metrics now clears stored metrics history along with live and in-memory metrics, and reconnecting views reconcile with the cleared history.
- Settings > Theme includes 10 built-in wallpapers in a carousel. Wallpapers and solid background colors apply immediately, and the WebUI waits for the selected wallpaper before showing the page. Buttons, menus, and panels use flatter surfaces without the previous reflection effect.
- Plugin controls show the backend operation state, and enable and disable notifications include the plugin name.
- On Windows, the launcher window follows the WebUI theme and interface scale and shows the WebUI startup screen while SoAI starts.
- The Updates page shows the notes for every published release between the installed and latest versions, renders their formatting, and identifies incomplete note history. During a self-update it shows preparation, download, verification, staging, and handoff progress when available.
- Windows in-app updates no longer depend on the desktop window staying open. A small update window stays on screen while the installer replaces SoAI and closes when the updated version opens. If the updater fails unexpectedly, it writes the error to `application_updater.stderr.log` in the SoAI logs folder and restarts the previous version.
- After an update, the WebUI reloads without stale cached files and each user sees once whether SoAI moved to the new version or kept the previous one. Browser tabs that stayed open during the update offer to reload.
- Model, backend, and update downloads retry temporary connection and server failures with bounded waits. Resumed transfers check that the retained bytes belong to the same file, and cancelling waits for active file writes to finish before freeing their storage. Network installers also retry temporary download failures, and Windows keeps a diagnostic record for each attempt.
- Model download progress reaches completion only once the model is ready, Ollama pulls require confirmed completion, and cTranslate2 converts models in a staging directory so an existing model stays intact.
- Long upload filenames keep their display names while the stored and temporary names fit the destination filesystem. Cancelling an upload waits for active file work, and if the database result is lost, the uploaded file is kept until SoAI can confirm whether the upload was accepted.
- The Windows installer has been improved and updated.
- Windows setup and complete-archive installation enable long-path support before preparing Python and preserve quoted installation arguments. Unsafe folders, conflicting launcher configuration, and unfinished update recovery are rejected before an existing installation is replaced.
- Startup and readiness waits allow more time on slow machines. The database writer, RAG startup, and document parsing have longer defaults, and a saved configuration that still uses the previous default values is upgraded once while other saved values stay unchanged.
- Updated Python dependencies: `python-dotenv` 1.2.3, `tinytag` 2.3.2, and `tqdm` 4.70.1.

### Fixes

- Streamed responses route provider errors to the correct operation and no longer repeat echoed prompt text at the start of the reply.
- OpenAI-compatible streams that request `stream_options.include_usage` now receive a single usage chunk before the end of the stream instead of usage reported twice.
- Saving several selected chat MCP tools at once keeps the full selection. Saved tools and servers that are currently unavailable are listed and kept rather than dropped from the selection.
- If your saved memory profile cannot be loaded, SoAI pauses saving so the stored profile is not overwritten. A voice call that fails now stops and explains why.
- Large file uploads no longer fail on a fixed overall time limit while data is still arriving.
- On slow or unreliable connections, the WebUI waits up to 90 seconds instead of 30 for the server, and a temporary network failure no longer discards the saved server address or your session. If startup or permission loading fails, the page shows a translated message with a Reload button.
- Compacting a conversation manually keeps the existing history when the summary would not be smaller, and reports that nothing was compacted. When compaction fails, the error now shows the actual cause, such as a model that is not loaded.
- Editing and saving prompts on the Prompts page, scrolling in the first-run wizard and in cloned conversations, and conversation PDF export work correctly again. Browser automation recovers more reliably from driver disconnects and shutdown races.
- Stopping a SoAIBench run also stops its child process. History tables keep existing rows visible while a GPU's runs reload, update individual rows in place, and ask for confirmation before deleting an eligible local run.
- On Windows, the Dashboard and Hardware pages list the network adapters that Windows shows, including disconnected and virtual adapters, and no longer include hidden ones. Hardware widgets keep their selected metrics when device ordering changes.
- Stop all in the header cancels queued requests before stopping plugins and cannot be started twice while it runs.
- Secret fields in desktop Microsoft Edge, including the Windows launcher, no longer show two reveal buttons. Background gradients no longer show banding in Firefox, and the update confirmation button uses the correct color.
- On Linux and macOS, SoAI keeps writing to its terminal and to the service logs after an in-place restart.
- The macOS network installer and service installation work with the system's Bash 3.2.
- Uninstalling SoAI on Windows waits for SoAI's own runtime processes to exit before removing files, and stops without removing anything if they are still running after 60 seconds.

### Plugin updates

- The llama.cpp and embedding plugins now install the llama.cpp v0.5.0 server release (build b11146).

### Upgrade notes

- The updated llama.cpp, embedding, vLLM, cTranslate2, and Ollama plugins require SoAI 1.3.0 or later, so update SoAI before installing these plugin versions. To replace an existing cTranslate2 model, delete it before starting the new download.
- On Windows, install this release with the setup program if SoAI 1.2.1 or earlier is installed. An in-app update started from those versions can stop before the installation begins; later in-app updates use the corrected process.

## 1.2.1

SoAI 1.2.1 improves installation and startup reliability after the 1.2.0 release, especially on slower machines and systems with older graphics drivers.

### Fixes

- The Windows PowerShell installation command now starts correctly when invoked through `irm | iex`. Runtime preparation waits longer for slow systems, checks required modules independently, and identifies the failed package or module when validation cannot complete.
- Installer retries keep separate diagnostic logs and preserve a failure bundle when runtime preparation fails, while rollback and cleanup leave the previous application files and user data in the declared state.
- Startup no longer treats an NVIDIA driver/NVML process-query mismatch as a fatal error on legacy GPUs; unavailable non-critical process metrics are reported as unavailable instead.
- The Windows launcher now cleans up its owned backend when startup or shutdown is interrupted. RAG startup and the llama.cpp browser installation path also allow more time on slower or inconsistent machines.

## 1.2.0

SoAI 1.2.0 brings a new SoAIBench scoring method and public leaderboard sharing, makes stopping and regenerating Chat responses more reliable, and improves streaming performance and attachment handling. It also adds per-user OCR language and activity timing preferences. Users can now choose which page SoAI opens when they connect to the WebUI; previously, it always opened the Dashboard.

### Highlights

- SoAIBench now warms up the GPU with active work for at least 120 seconds before running 5 measured passes. The overall score weights compute throughput at 40% and memory throughput at 60%, while latency remains available as a separate measurement.
- Completed eligible results can be shared from the WebUI to the public SoAIBench leaderboard. We welcome new GPU scores, especially for models that are not represented yet.
- Chat Stop remains tied to the response you intended to stop, including during reconnects, page reloads, and activity in another browser tab.
- Regenerate can recover an accepted request after an interrupted connection without generating the same reply twice. SoAI also prevents conflicting sends, edits, deletions, compactions, and regenerations from changing the conversation at the same time.

### SoAIBench

- Before sharing a score, SoAI shows what will be sent: the benchmark result, 5 measured passes, public GPU and runtime information, benchmark settings, and available sensor readings. It does not include account identity, files, configuration, analytics, or unrelated telemetry.
- Benchmark startup, stopping, and recovery are more reliable. Interrupted runs no longer leave the GPU busy, and retrying a share after a timeout reconciles the original attempt instead of creating another submission.
- GPU matching works more reliably when a system exposes the same NVIDIA, AMD, or Intel device through more than one OpenCL platform. One OpenCL session is reused across the benchmark so setup work stays outside the measurements.
- History has clearer diagnostics, stable headers while scrolling, and improved sorting. Copy and download reports now include compute and memory scores, utilization, sample counts, and run guidance when available. Unpublished completed runs can be removed from local history, while runs prepared for or sent to the leaderboard are kept so SoAI can reconcile their publication state.
- Earlier scores remain in history, but the changed warm-up, measurements, and score weighting mean they should not be compared directly with scores created by this release.

### Chat, attachments, and assistant activity

- Long streaming responses perform less repeated rendering, which reduces Markdown movement and browser work without delaying live text or activity updates.
- The loading activity can be expanded or collapsed while a response is running. When collapsed, it continues to show what the model is doing in real time without displaying every individual activity and its details. Under Chat configuration > Appearance, turning off Show activities elapsed time stops the running timer updates but still shows the final duration when an activity ends.
- Saved attachments are checked before SoAI serves their content. A file that is missing or no longer matches its saved record is shown as unavailable with a prompt to upload it again.
- Attachment cards, overflow browsing, thumbnails, camera capture, and composer resizing behave more consistently on desktop and compact layouts.
- Reloading Chat, reconnecting, switching tabs, or deleting a conversation no longer duplicates, hides, or incorrectly revives active work.

### WebUI and preferences

- Settings now has a separate OCR extraction language for each user. Fresh setup initializes it from the selected interface language, and a saved change applies to future Tesseract extraction without a restart. Changing it does not reprocess text that SoAI has already extracted, and RapidOCR keeps its existing priority.
- Users can now choose which page SoAI opens when they connect to the WebUI. Previously, SoAI always opened the Dashboard. If the selected page becomes unavailable or inaccessible, SoAI opens the Dashboard instead.
- Large collections and the Models page update more smoothly. External models use a Cloud badge, provider discovery gives clearer progress and errors, and request distribution charts adapt to the data being shown.
- Task cancellation reaches the operation that owns the work, including plugin operations, and the task panel no longer shows duplicate stop controls.
- Chat controls, search fields, notifications, the sidebar, and empty states have more consistent behavior across narrow and short screens.

### Platform and plugin fixes

- Windows file checks no longer confuse distinct files, conversation PDF export waits until the document is ready, and SoAIBench uses the correct Windows OpenCL library loading path.
- Changing the interface language no longer leaves parts of the WebUI in different languages if the new catalog cannot be loaded or saved.
- Backend variant discovery handles missing plugins and delayed catalog updates without dropping valid choices.
- The llama.cpp, Embedding, and vLLM plugins are updated to version 1.1.1 with stricter browser CORS defaults. A browser that connects directly to one of these plugin backends must use an allowed origin.

### Upgrade notes

- The database migration preserves conversations, settings, attachments, and SoAIBench history while adding the records needed for reliable regeneration and score sharing. Create and verify a backup before updating.

## 1.1.1

SoAI 1.1.1 changes Windows uninstall so it keeps application data by default, fixes several status and messaging controls in the WebUI, and keeps model and plugin state current through delayed events and restarts. OpenAI-compatible streamed responses now preserve multiple choices and their metadata.

### Highlights

- The Windows uninstaller now preserves application data by default. Users who want a complete removal can select an explicit option to delete accounts, configuration, chats, models, files, logs, and backups.
- The WebUI reports system activity more accurately, including a distinct maintenance state and the correct runtime state for each model. Chat configuration also keeps a stable loading view until its settings are ready.
- Plugin state and recovery now preserve the latest durable state across restarts and delayed events, preventing older events from replacing current status or triggering stale recovery work.

### Improvements

- The Windows launcher isolates the bundled Python environment from settings inherited from the host. When startup fails, it records the backend exit code and recent output so the cause is easier to find.
- Prompt previews show the last-updated date and time. Long collections such as chats, files, models, plugins, and prompts now render 72 entries per page instead of 48, keeping more items in the active scrolling window.
- OpenAI-compatible streamed responses now keep each choice's content and metadata independent, including reasoning, tool calls, token probabilities, usage, and performance measurements. Invalid provider output and malformed Responses API requests are rejected with safe public errors.
- Model and plugin downloads validate resumed byte ranges before accepting them, preserving the last complete file when a server returns mismatched or incomplete data. Model variant discovery also gives clearer errors for invalid selections, missing repositories, access problems, and provider outages.
- Duplicate model-start requests now share the active launch instead of starting the same plugin twice. Startup failures clean up owned backend processes and distinguish invalid settings from failures that can use failover, while plugin configuration reads use the latest saved values rather than a stale cached copy.
- Real-time WebUI connections close when event delivery fails instead of continuing with apparently current data. The sidebar also avoids false reconnecting or offline flashes during refreshes, cancelled navigation, and successful reconnection.

### Fixes

- The Windows installer now provisions the Visual C++ runtime files needed by SoAI's bundled Python environment before dependency setup. Fresh Windows systems can install and start SoAI even when the Microsoft Visual C++ Runtime was not already present.
- Enabling or disabling a Messaging account now applies the requested lifecycle change. Conflicts, failed provider activation, and accounts changed from another session produce a visible result instead of a misleading success state.
- Model cards now attach starting, loading, processing, and stopping states only to the model using that backend process. External provider models also show real error and stopping states instead of being displayed as available.
- Streaming responses are no longer stopped early by a second approximate token-limit check after the model backend has already applied the request limit.
- The chat configuration modal no longer mixes section-level and preset-level loading indicators or exposes controls before their saved values have loaded.

### Plugin updates

- The vLLM plugin is updated to version 1.1.0 and supports vLLM 0.29.0, with installation profiles for CPU, CUDA 12.9 and 13.0, ROCm 7.2.3, Metal, TPU, and XPU.
- The llama.cpp and Embedding plugins are updated to version 1.1.0 and use llama.cpp b10909, with updated model parameters and artifact handling.
- The External plugin is updated to version 1.0.2. Model discovery tolerates incomplete provider model lists, and failed streamed requests retain the useful upstream HTTP error when the response body cannot be read.

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
