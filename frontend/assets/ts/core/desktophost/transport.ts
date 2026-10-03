/* SoAI - Native desktop host message transport [frontend/assets/ts/core/desktophost/transport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const resolveDesktopHostTransport = (): ChromeWebViewTransport | null => {
    const transport = window.chrome?.webview;
    return transport && typeof transport.postMessage === 'function' && typeof transport.addEventListener === 'function' ? transport : null;
};

export { resolveDesktopHostTransport };
