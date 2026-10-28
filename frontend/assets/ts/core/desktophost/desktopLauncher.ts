/* SoAI - Native desktop launcher host integration [frontend/assets/ts/core/desktophost/desktopLauncher.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveDesktopHostTransport } from '@core/desktophost/transport.ts';
import { getDocumentElement, getEventHub, getMutationObserverCtor } from '@core/environment/public.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';

const DESKTOP_LAUNCHER_CHANNEL = 'soai.desktopLauncher.v1';
const DESKTOP_LAUNCHER_PLATFORMS: ReadonlySet<string> = new Set(['windows', 'linux', 'macos']);
const THEME_PREFERENCES: ReadonlySet<string> = new Set(['light', 'dark', 'auto']);
const INTERFACE_SCALES: ReadonlySet<number> = new Set([50, 75, 100, 125, 150]);
const MAX_BOOT_STATUS_LENGTH = 2000;
const BOOT_CLOCK_TOLERANCE_MS = 1000;

interface DesktopLauncherBootHandoff {
    readonly startedAt: number;
    readonly status: string;
}

interface DesktopLauncherAppearance {
    preference: string;
    theme: 'light' | 'dark';
    interfaceScale: number;
}

const isDesktopLauncherHost = (): boolean => {
    const capability = window.soaiDesktopLauncher;
    return capability !== undefined && DESKTOP_LAUNCHER_PLATFORMS.has(capability.platform) && capability.protocolVersion === 1 && resolveDesktopHostTransport() !== null;
};

const postDesktopLauncherMessage = (message: Record<string, string | number>): void => {
    const transport = resolveDesktopHostTransport();
    if (!isDesktopLauncherHost() || !transport) return;
    transport.postMessage(JSON.stringify({ channel: DESKTOP_LAUNCHER_CHANNEL, ...message }));
};

const announceDesktopLauncherUpdateHandoff = (targetVersion: string): void => {
    postDesktopLauncherMessage({ command: 'updateHandoff', targetVersion });
};

const resolveDesktopLauncherBootHandoff = (): DesktopLauncherBootHandoff | null => {
    const handoff = window.soaiDesktopLauncherBoot;
    if (!handoff || !isDesktopLauncherHost()) return null;
    const { startedAt, status } = handoff;
    if (typeof startedAt !== 'number' || !Number.isFinite(startedAt) || startedAt <= 0 || startedAt > Date.now() + BOOT_CLOCK_TOLERANCE_MS) return null;
    if (typeof status !== 'string' || status.length > MAX_BOOT_STATUS_LENGTH) return null;
    return { startedAt, status };
};

const announceDesktopLauncherBootReveal = (): void => {
    postDesktopLauncherMessage({ command: 'bootReveal' });
};

const registerDesktopLauncherDetachedContextCapture = (capture: () => JsonObject | null): (() => void) => {
    if (!isDesktopLauncherHost()) return () => {};
    const handleCapture = (event: Event): void => {
        if (event instanceof CustomEvent && isJsonObject(event.detail)) event.detail['context'] = capture();
    };
    getEventHub().addEventListener('soai:desktop-detached-context-capture', handleCapture);
    return () => getEventHub().removeEventListener('soai:desktop-detached-context-capture', handleCapture);
};

const takeDesktopLauncherDetachedContext = (): JsonObject | null => {
    if (!isDesktopLauncherHost()) return null;
    const context = window.soaiDesktopLauncherDetachedContext;
    delete window.soaiDesktopLauncherDetachedContext;
    if (context !== undefined && context !== null && !isJsonObject(context)) throw new Error('Desktop detached context must be an object');
    return isJsonObject(context) ? context : null;
};

const readAppearance = (preference: string): DesktopLauncherAppearance => {
    const root = getDocumentElement();
    const interfaceScale = Number(root.getAttribute('data-interface-scale'));
    return {
        preference: THEME_PREFERENCES.has(preference) ? preference : 'dark',
        theme: root.classList.contains('theme-light') ? 'light' : 'dark',
        interfaceScale: INTERFACE_SCALES.has(interfaceScale) ? interfaceScale : 100
    };
};

const readThemeChangedPreference = (event: Event): string | null => {
    if (!(event instanceof CustomEvent) || !isJsonObject(event.detail)) return null;
    const theme = event.detail['theme'];
    return typeof theme === 'string' && THEME_PREFERENCES.has(theme) ? theme : null;
};

const startDesktopLauncherAppearanceSync = (): void => {
    if (!isDesktopLauncherHost()) return;
    const root = getDocumentElement();
    let preference = root.dataset['soaiThemePreference'] ?? 'dark';
    let published = '';
    const publishAppearance = (): void => {
        const appearance = readAppearance(preference);
        const snapshot = JSON.stringify(appearance);
        if (snapshot === published) return;
        published = snapshot;
        postDesktopLauncherMessage({ command: 'appearance', ...appearance });
    };
    const handleThemeChanged = (event: Event): void => {
        preference = readThemeChangedPreference(event) ?? preference;
        publishAppearance();
    };
    getEventHub().addEventListener('themeChanged', handleThemeChanged);
    const MutationObserverCtor = getMutationObserverCtor();
    new MutationObserverCtor(publishAppearance).observe(root, { attributes: true, attributeFilter: ['class', 'data-interface-scale'] });
    publishAppearance();
};

export { announceDesktopLauncherBootReveal, announceDesktopLauncherUpdateHandoff, isDesktopLauncherHost, registerDesktopLauncherDetachedContextCapture, resolveDesktopLauncherBootHandoff, startDesktopLauncherAppearanceSync, takeDesktopLauncherDetachedContext };
export type { DesktopLauncherBootHandoff };
