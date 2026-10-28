# SoAI Windows Release Tools

This folder contains the first-party code and manifests used to build the SoAI launcher, complete Windows archive, and Windows installer. In the public source tree it does not bundle NSIS, Python, WebView2, or other third-party software.

## Layout

- `launcher/` contains the C# WinForms/WebView2 launcher source and build script. The script compiles with the .NET Framework C# compiler when present, or otherwise with the Roslyn compiler bundled with PowerShell 7 against pinned .NET Framework 4.8 reference assemblies, which lets the release build run under Wine.
- `installer/` contains the NSIS script, installer assets, and runtime install/uninstall helper scripts.
- `tools/` contains payload staging, canonical archive creation, installer asset generation, and verified NSIS bootstrap tooling.
- `build-release.ps1` builds the launcher, stages and archives the Windows payload, and invokes NSIS.
- `dependencies-v1.json` pins downloadable build and runtime dependencies and their integrity policy.

## Runtime Behavior

The installer copies the SoAI payload, installs Microsoft Edge WebView2 Evergreen Runtime when missing, installs the pinned Python 3.13 runtime without adding it to PATH, creating file associations, or registering a system Python install, prepares the managed venv, installs Python dependencies, provisions runtime artifacts, runs the post-update hook, and writes Start Menu, Desktop, and uninstall entries. Current releases use a SHA-256-pinned Python Build Standalone archive from Astral; the runtime installer also accepts the existing NuGet package layout. It validates a staged replacement before removing the previous runtime and requires both the base interpreter and managed venv to report the declared version before recording installation success.

After installation, `soai.exe install-deps` remains the supported dependency repair/update path. The launcher starts that command from the bundled app-local Python runtime, then SoAI relaunches into the managed venv to update requirements, runtime artifacts, and migration hooks.

The uninstaller stops SoAI, removes shortcuts and registry entries, removes files listed in the generated install manifest, and removes known SoAI-owned runtime/data directories. It guards against dangerous roots and avoids deleting unrelated files placed beside the install.

The complete archive contains the same compiled `soai.exe` launcher and validated Windows payload as the installer. After verification and extraction, `install-soai-from-release.bat --target C:\path\to\SoAI --silent` bootstraps the app-local runtime, copies the managed payload to the selected target, and provisions that target. Its archive uninstall mode removes only the selected deployment and does not remove installer-created global integration.
