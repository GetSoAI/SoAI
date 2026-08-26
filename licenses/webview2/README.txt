Microsoft Edge WebView2 Runtime notice

SoAI may include Microsoft Edge WebView2 Runtime as a separate third-party runtime dependency for the native Windows launcher. The WebView2 Runtime is not first-party SoAI code and is not licensed under the SoAI Source-Available License 1.0 or SoAI commercial license.

Source:
https://developer.microsoft.com/en-us/microsoft-edge/webview2/

Distribution guidance:
https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution

Runtime packaging in this build:
The Windows installer installs the Microsoft Edge WebView2 Evergreen Runtime when it is missing. The native launcher bundles Microsoft.Web.WebView2 SDK assemblies required to host WebView2, but this source package does not bundle a fixed WebView2 runtime.

Packaging notes for the installer:
- Download or install the runtime directly from Microsoft.
- Keep the runtime as object-code binaries only and do not modify it.
- Preserve Microsoft and third-party notices.
- Do not imply Microsoft endorses SoAI.
- Treat the runtime as a separate dependency from the SoAI Licensed Work.
- If a future build uses a fixed runtime, apply AppContainer read/execute ACLs to the fixed runtime folder on Windows when installed unpackaged.
