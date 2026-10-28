/* SoAI - Current backend information and badge synchronization [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/backendInfo.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { MANAGE_BACKEND_MODAL_ID } from '@features/plugins/modals/backendModals.ts';
import { renderManageBackendBadge, type ManageBackendBadgeState } from '@features/plugins/modals/backend/managebackendmodal/backendBadge.ts';

interface BackendInfoView {
    optionalHTMLElement(selector: string, context?: Element): HTMLElement | null;
    updateText(target: Element | string, text: string): void;
}

interface BackendInfoStatus {
    getPluginStatus(plugin: PluginRecord): string;
    getBackendStatus(plugin: PluginRecord): string;
    getBackendVersion(plugin: PluginRecord): string;
}

interface BackendInfoIndicator {
    updateIndicator(element: HTMLElement, status: string): void;
}

const renderManageBackendInfoStatus = (view: BackendInfoView, status: BackendInfoStatus, plugin: PluginRecord, modalRoot: HTMLElement, indicator: BackendInfoIndicator | null, state?: ManageBackendBadgeState, catalogFresh?: boolean): void => {
    const badge = view.optionalHTMLElement('.plugin-install-badge', modalRoot);
    if (!badge) throw new Error('Backend information requires a lifecycle badge');
    const presentation = renderManageBackendBadge(badge, status.getPluginStatus(plugin), state, catalogFresh);
    const led = view.optionalHTMLElement(modalUiSelector(MANAGE_BACKEND_MODAL_ID, 'info-led'), modalRoot);
    if (led) indicator?.updateIndicator(led, presentation.pluginStatus);
    const statusElement = view.optionalHTMLElement('.plugin-info-status', modalRoot);
    if (statusElement) view.updateText(statusElement, i18n.t('plugins.modal.manageBackend.backendStatus', { status: presentation.backendStatus ?? status.getBackendStatus(plugin) }));
    const versionElement = view.optionalHTMLElement('.plugin-backend-version', modalRoot);
    if (versionElement) view.updateText(versionElement, i18n.t('plugins.modal.manageBackend.backend_version', { version: status.getBackendVersion(plugin) || i18n.t('common.unknown') }));
};

export { renderManageBackendInfoStatus };
