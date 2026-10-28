/* SoAI - Plugin modal LED state updates [frontend/assets/ts/features/plugins/modals/pluginsModalLedUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { renderManageBackendInfoStatus } from '@features/plugins/modals/backend/managebackendmodal/backendInfo.ts';
import { MANAGE_BACKEND_MODAL_ID } from '@features/plugins/modals/backendModals.ts';

interface PluginStatusIndicatorHost {
    updateIndicator(element: HTMLElement, status: string): void;
}

interface PluginsModalLedUpdateHost {
    modals: ModalPresenterApi;
    optionalHTMLElement(selector: string, context?: Element): HTMLElement | null;
    updateText(target: Element | string, text: string): void;
    getPluginStatus(plugin: PluginRecord): string;
    getBackendStatus(plugin: PluginRecord): string;
    getBackendVersion(plugin: PluginRecord): string;
    statusManager: PluginStatusIndicatorHost;
    getCurrentManagingPlugin(): PluginRecord | null;
    setInterval(callback: () => void, delay: number): number | null;
    clearTimer(timerId: number): void;
}

const updatePluginsModalLeds = (host: PluginsModalLedUpdateHost): void => {
    const currentManagingPlugin = host.getCurrentManagingPlugin();
    if (currentManagingPlugin) {
        const modalRoot = host.modals.requireElement(MANAGE_BACKEND_MODAL_ID);
        renderManageBackendInfoStatus(host, host, currentManagingPlugin, modalRoot, host.statusManager);
    }
};

const startPluginsModalLedUpdates = (host: PluginsModalLedUpdateHost): number => {
    updatePluginsModalLeds(host);
    const timer = host.setInterval(() => updatePluginsModalLeds(host), 1000);
    if (timer === null) {
        throw new Error('PluginsPage failed to start modal LED update timer');
    }
    return timer;
};

const stopPluginsModalLedUpdates = (host: PluginsModalLedUpdateHost, timerId: number | null): number | null => {
    if (timerId === null) {
        return null;
    }
    host.clearTimer(timerId);
    return null;
};

export { startPluginsModalLedUpdates, stopPluginsModalLedUpdates };
export type { PluginsModalLedUpdateHost };
