# SoAI Windows Release Tools

This folder contains the first-party code and manifests used to build the SoAI launcher, complete Windows archive, and Windows installer. In the public source tree it does not bundle NSIS, Python, WebView2, or other third-party software. The generated Windows build kit adds the pinned NSIS toolchain and its license so the installer can be built offline.

## Layout

- `launcher/` contains the C# WinForms/WebView2 launcher source and build script.
- `installer/` contains the NSIS script, installer assets, and runtime install/uninstall helper scripts.
- `tools/` contains payload staging, canonical archive creation, installer asset generation, and verified NSIS bootstrap tooling.
- `build-release.ps1` builds the launcher, stages and archives the Windows payload, and invokes NSIS.
- `dependencies-v1.json` pins downloadable build and runtime dependencies and their integrity policy.

## Expected Input

Run these tools on a Windows release machine with a separately extracted SoAI Windows build kit. The build-kit root must contain `backend`, `frontend`, `plugins`, `VERSION`, `requirements.txt`, `install-soai-from-release.bat`, and the release documents. It does not need to contain Python, a virtual environment, WebView2 Runtime, or NSIS.

## Build

From the public source tree, build against the extracted build kit:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\tools\windows-release\tools\Bootstrap-NSIS.ps1
.\tools\windows-release\tools\New-InstallerAssets.ps1 -LogoPath C:\build-kit\frontend\assets\img\soai\soai-logo-small-dark.png
.\tools\windows-release\build-release.ps1 -SourceRoot C:\build-kit
```

The build reads the product version only from the build kit's `VERSION` file. Output is written under `tools\windows-release\out` by default. It produces `SoAI-<version>-windows-x64-complete.zip` and `SoAI-<version>-windows-x64-setup.exe` together; a failed installer build removes the incomplete release pair.

## Runtime Behavior

The installer copies the SoAI payload, installs Microsoft Edge WebView2 Evergreen Runtime when missing, downloads the configured Python 3.13 NuGet runtime package into the SoAI install directory without adding it to PATH, creating file associations, or registering a system Python install, prepares the managed venv, installs Python dependencies, provisions runtime artifacts, runs the post-update hook, and writes Start Menu, Desktop, and uninstall entries.

After installation, `soai.exe install-deps` remains the supported dependency repair/update path. The launcher starts that command from the bundled app-local Python runtime, then SoAI relaunches into the managed venv to update requirements, runtime artifacts, and migration hooks.

The uninstaller stops SoAI, removes shortcuts and registry entries, removes files listed in the generated install manifest, and removes known SoAI-owned runtime/data directories. It guards against dangerous roots and avoids deleting unrelated files placed beside the install.

The complete archive contains the same compiled `soai.exe` launcher and validated Windows payload as the installer. After verification and extraction, `install-soai-from-release.bat --target C:\path\to\SoAI --silent` bootstraps the app-local runtime, copies the managed payload to the selected target, and provisions that target. Its archive uninstall mode removes only the selected deployment and does not remove installer-created global integration.
