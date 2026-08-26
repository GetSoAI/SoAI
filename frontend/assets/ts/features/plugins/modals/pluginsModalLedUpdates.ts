/* SoAI - Plugin modal LED state updates [frontend/assets/ts/features/plugins/modals/pluginsModalLedUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
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
    currentManagingPlugin: PluginRecord | null;
    setInterval(callback: () => void, delay: number): number | null;
    clearTimer(timerId: number): void;
}

const updatePluginsModalLeds = (host: PluginsModalLedUpdateHost): void => {
    if (host.currentManagingPlugin) {
        const modalRoot = host.modals.requireElement(MANAGE_BACKEND_MODAL_ID);
        const manageLed = host.optionalHTMLElement(modalUiSelector(MANAGE_BACKEND_MODAL_ID, 'info-led'), modalRoot);
        if (manageLed) {
            host.statusManager.updateIndicator(manageLed, host.getPluginStatus(host.currentManagingPlugin));
        }
        const backendStatus = host.getBackendStatus(host.currentManagingPlugin);
        const statusElement = host.optionalHTMLElement('.plugin-info-status', modalRoot);
        if (statusElement) {
            host.updateText(statusElement, i18n.t('plugins.modal.manageBackend.backendStatus', { status: backendStatus }));
        }
        const backendVersion = host.getBackendVersion(host.currentManagingPlugin) || i18n.t('common.unknown');
        const versionElement = host.optionalHTMLElement('.plugin-backend-version', modalRoot);
        if (versionElement) {
            host.updateText(versionElement, i18n.t('plugins.modal.manageBackend.backend_version', { version: backendVersion }));
        }
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
