/* SoAI - Shared layout version [frontend/assets/ts/core/layout/sidebar/version.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { getBranding } from '@core/branding/public.ts';
import { requireConnectionStatus, type ConnectionEvent } from '@core/connectionstatus/public.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ARIA_HIDDEN_ATTR, STYLE_DISPLAY, STYLE_OPACITY } from '@core/layout/sidebar/dom.ts';
import { extractSidebarVersionFromSystemInfo, normalizeSidebarVersionValue } from '@core/layout/sidebar/mappers.ts';
import { decodeSystemInfo } from '@core/api/contracts/systemContracts.ts';

type SidebarVersionDomRefKey = 'logoLarge' | 'logoSmall' | 'versionSmall' | 'versionLarge';

interface SidebarVersionDisplayState {
    collapsed: boolean;
    mobile: boolean;
    open: boolean;
}

interface SidebarVersionHost {
    getDisplayState: () => SidebarVersionDisplayState;
    getDomRef: (key: SidebarVersionDomRefKey) => HTMLElement | null;
}

class SidebarVersionController {
    readonly #host: SidebarVersionHost;

    #systemVersion: string | null = null;
    #versionTask: Promise<void> | null = null;
    #systemInfoUnsubscribe: (() => void) | null = null;

    constructor(host: SidebarVersionHost) {
        this.#host = host;
    }

    destroy(): void {
        this.clearSystemInfoSubscription();
        this.#versionTask = null;
        this.#systemVersion = null;
    }

    refreshVisibility(): void {
        const state = this.#host.getDisplayState();
        const smallMode = state.mobile ? !state.open : state.collapsed;

        const updateVisibility = (element: HTMLElement | null, visible: boolean): void => {
            if (element) {
                dom.setData(element, 'visible', String(visible));
                dom.setAttribute(element, ARIA_HIDDEN_ATTR, String(!visible));
                dom.setStyle(element, STYLE_OPACITY, visible ? '1' : '0');
            }
        };

        updateVisibility(this.#host.getDomRef('logoLarge'), !smallMode);
        updateVisibility(this.#host.getDomRef('logoSmall'), smallMode);

        const logoLarge = this.#host.getDomRef('logoLarge');
        if (logoLarge instanceof HTMLImageElement) {
            getBranding().updateLogoElement(logoLarge, 'ui');
        }
        const logoSmall = this.#host.getDomRef('logoSmall');
        if (logoSmall instanceof HTMLImageElement) {
            getBranding().updateLogoElement(logoSmall, 'small');
        }

        this.updateVersionVisibility(smallMode);
    }

    async initializeSources(): Promise<void> {
        if (this.#versionTask) return this.#versionTask;
        const task = (async (): Promise<void> => {
            await Promise.allSettled([this.fetchVersionFromAPI(), this.setupSystemInfoListener()]);
        })();
        terminateHandledPromise(
            task.finally(() => {
                if (this.#versionTask === task) this.#versionTask = null;
            })
        );
        this.#versionTask = task;
        return task;
    }

    async fetchVersionFromAPI(): Promise<void> {
        try {
            const info = await requestWebSocketSnapshotRecord('system.info');
            this.applySystemVersion(decodeSystemInfo(info).soaiVersion);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('Sidebar', 'Version fetch failed', runtimeError);
        }
    }

    async setupSystemInfoListener(): Promise<void> {
        if (this.#systemInfoUnsubscribe) return;
        try {
            const connectionStatus = requireConnectionStatus();
            if (!isFunction(connectionStatus.subscribe)) return;
            const handler = (eventValue: ConnectionEvent): void => {
                if (isObject(eventValue.systemInfo)) {
                    this.applySystemVersion(extractSidebarVersionFromSystemInfo(eventValue.systemInfo));
                }
            };
            const unsubscribe = connectionStatus.subscribe(handler, { emitCurrent: true });
            if (isFunction(unsubscribe)) {
                this.#systemInfoUnsubscribe = unsubscribe;
            }

            if (isFunction(connectionStatus.getSnapshot)) {
                const snapshot = connectionStatus.getSnapshot();
                if (snapshot !== null && isObject(snapshot.systemInfo)) {
                    this.applySystemVersion(extractSidebarVersionFromSystemInfo(snapshot.systemInfo));
                }
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('Sidebar', 'System info listener setup failed', runtimeError);
        }
    }

    clearSystemInfoSubscription(): void {
        if (!this.#systemInfoUnsubscribe) return;
        try {
            this.#systemInfoUnsubscribe();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('Sidebar', 'System info monitor cleanup failed', runtimeError);
        }
        this.#systemInfoUnsubscribe = null;
    }

    applySystemVersion(version: string | null): void {
        const normalized = normalizeSidebarVersionValue(version);
        if (normalized && normalized !== this.#systemVersion) {
            this.#systemVersion = normalized;
            this.refreshVisibility();
        }
    }

    updateVersionVisibility(smallMode: boolean): void {
        if (!this.#systemVersion) return;
        const text = `SoAI v${this.#systemVersion}`;
        const small = this.#host.getDomRef('versionSmall');
        const large = this.#host.getDomRef('versionLarge');
        const set = (element: HTMLElement | null, visible: boolean): void => {
            if (element) {
                dom.setText(element, text);
                dom.setStyles(element, {
                    [STYLE_DISPLAY]: visible ? 'block' : 'none',
                    [STYLE_OPACITY]: visible ? '0.7' : '0'
                });
                dom.setAttribute(element, ARIA_HIDDEN_ATTR, String(!visible));
            }
        };
        set(small, smallMode);
        set(large, !smallMode);
    }
}

export { SidebarVersionController };
export type { SidebarVersionDomRefKey, SidebarVersionDisplayState, SidebarVersionHost };
