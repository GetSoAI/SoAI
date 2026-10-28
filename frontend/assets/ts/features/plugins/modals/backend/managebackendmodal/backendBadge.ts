/* SoAI - Backend information badge lifecycle presentation [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/backendBadge.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { PLUGIN_STATUS_BACKEND_INSTALLING, PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR, PLUGIN_STATUS_BACKEND_UPDATING, PLUGIN_STATUS_INSTALL_ERROR, PLUGIN_STATUS_LOAD_ERROR, PLUGIN_STATUS_REMOVING_BACKEND, PLUGIN_STATUS_UNKNOWN, PLUGIN_STATUS_UPDATE_ERROR } from '@core/state/pluginStatus.ts';
import { renderInlineLoadingStatus } from '@core/ui/loadingStatus.ts';

type ManageBackendBadgeState = 'loading' | 'load-error' | 'ready' | 'installing' | 'updating' | 'uninstalling';

const readRequestedState = (badge: HTMLElement): ManageBackendBadgeState => {
    const state = badge.dataset['requestedState'];
    if (state === 'loading' || state === 'load-error' || state === 'installing' || state === 'updating' || state === 'uninstalling') return state;
    return 'ready';
};

const renderManageBackendBadge = (badge: HTMLElement, pluginStatus: string, state?: ManageBackendBadgeState, catalogFresh?: boolean): { pluginStatus: string; backendStatus: string | null } => {
    if (state !== undefined) badge.dataset['requestedState'] = state;
    if (catalogFresh !== undefined) badge.toggleAttribute('data-catalog-stale', !catalogFresh);
    const requested = readRequestedState(badge);
    const localOperation = requested === 'installing' || requested === 'updating' || requested === 'uninstalling';
    badge.toggleAttribute('data-local-backend-operation', localOperation);
    const operation = localOperation ? requested : pluginStatus === PLUGIN_STATUS_BACKEND_INSTALLING ? 'installing' : pluginStatus === PLUGIN_STATUS_BACKEND_UPDATING ? 'updating' : pluginStatus === PLUGIN_STATUS_REMOVING_BACKEND ? 'uninstalling' : null;
    let badgeState: string | null = null;
    let text = '';
    let loading = false;
    let displayStatus = pluginStatus;
    let backendStatus: string | null = null;
    if (badge.hasAttribute('data-catalog-stale') || pluginStatus === PLUGIN_STATUS_UNKNOWN) {
        badgeState = 'unknown';
        text = i18n.t('common.unknown');
        displayStatus = PLUGIN_STATUS_UNKNOWN;
        backendStatus = text;
    } else if (operation === 'installing') {
        badgeState = 'installing';
        displayStatus = PLUGIN_STATUS_BACKEND_INSTALLING;
        backendStatus = i18n.t('plugins.status.installing');
        text = `${i18n.t('plugins.loading.installingBackend')}...`;
        loading = true;
    } else if (operation === 'updating') {
        badgeState = 'updating';
        displayStatus = PLUGIN_STATUS_BACKEND_UPDATING;
        backendStatus = i18n.t('plugins.status.updating');
        text = `${i18n.t('plugins.loading.updatingBackend')}...`;
        loading = true;
    } else if (operation === 'uninstalling') {
        badgeState = 'uninstalling';
        displayStatus = PLUGIN_STATUS_REMOVING_BACKEND;
        backendStatus = i18n.t('plugins.loading.uninstallingBackend');
        text = `${i18n.t('plugins.loading.uninstallingBackend')}...`;
        loading = true;
    } else if (pluginStatus === PLUGIN_STATUS_INSTALL_ERROR || pluginStatus === PLUGIN_STATUS_UPDATE_ERROR || pluginStatus === PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR || pluginStatus === PLUGIN_STATUS_LOAD_ERROR) {
        badgeState = 'failed';
        text = pluginStatus === PLUGIN_STATUS_INSTALL_ERROR ? i18n.t('plugins.status.installError') : pluginStatus === PLUGIN_STATUS_UPDATE_ERROR ? i18n.t('plugins.status.updateError') : pluginStatus === PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR ? i18n.t('plugins.status.backendUninstallError') : i18n.t('plugins.status.loadError');
    } else if (requested === 'loading') {
        badgeState = 'loading';
        text = i18n.t('plugins.modal.backendVariants.loadingBackends');
        loading = true;
    } else if (requested === 'load-error') {
        badgeState = 'load-error';
        text = i18n.t('plugins.modal.backendVariants.loadFailed');
    } else if (pluginStatus === PLUGIN_STATUS_BACKEND_NOT_INSTALLED) {
        badgeState = 'needs-install';
        text = i18n.t('plugins.modal.installBackend.needsInstall');
    }
    if (badgeState) badge.dataset['state'] = badgeState;
    else delete badge.dataset['state'];
    badge.setAttribute('aria-busy', String(loading));
    renderInlineLoadingStatus(badge, { text, loading });
    return { pluginStatus: displayStatus, backendStatus };
};

export { renderManageBackendBadge };
export type { ManageBackendBadgeState };
