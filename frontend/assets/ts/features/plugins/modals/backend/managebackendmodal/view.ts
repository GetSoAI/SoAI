/* SoAI - Plugins feature manage backend modal rendering [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { getPluginSystemRequirementMessages } from '@core/plugins/systemRequirements.ts';
import { PLUGIN_STATUS_BACKEND_INSTALLING, PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_BACKEND_UPDATING, PLUGIN_STATUS_INSTALL_ERROR } from '@core/state/pluginStatus.ts';
import type { PluginBackendUpdateStatus } from '@core/api/contracts/pluginManagementContracts.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { setElementDisabledState } from '@features/plugins/contracts/pluginPageSupport.ts';
import type { BackendManagerSecurity } from '@features/plugins/modals/backend/backendTypes.ts';
import { bindBackendWebsiteLinkClick } from '@features/plugins/modals/backend/backendWebsiteLinkEvents.ts';
import { buildBackendWebsiteLink, getBackendWebsiteUrl } from '@features/plugins/modals/backend/backendWebsiteLink.ts';
import { setBackendVariantSelectorDisabled } from '@features/plugins/modals/backend/backendVariantSelector.ts';
import type { ManageBackendManagerHost, ManageClassNames, ManageState } from '@features/plugins/modals/backend/managebackendmodal/types.ts';

interface ManageInfoViewDependencies {
    host: ManageBackendManagerHost;
    security: BackendManagerSecurity;
}

interface ManageButtonsViewDependencies {
    host: ManageBackendManagerHost;
    classNames: ManageClassNames;
}

interface ManageUpdateViewDependencies extends ManageButtonsViewDependencies {
    host: ManageBackendManagerHost;
    state: ManageState;
    security: BackendManagerSecurity;
}

const renderManageBackendInfo = (dependencies: ManageInfoViewDependencies, modalId: string, modalRoot: HTMLElement, plugin: PluginRecord): void => {
    const info = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'plugin-info'), modalRoot);
    const unknown = i18n.t('common.unknown');
    const name = String(plugin.displayName ?? '').trim() || dependencies.host.operations.formatPluginName(String(plugin.name)) || unknown;

    const backendVersion = dependencies.host.status.getBackendVersion(plugin);
    const pluginVersion = String(plugin.versionSoaiplugin ?? '').trim() || i18n.t('common.notAvailableShort');
    const author = String(plugin.authorSoaiplugin ?? '').trim() || unknown;
    const backendStatus = dependencies.host.status.getBackendStatus(plugin) || unknown;

    const esc = (value: string): string => dependencies.security.escapeHtml(value);
    const ledId = modalUiId(modalId, 'info-led');
    const websiteLinkId = modalUiId(modalId, 'website-link');
    const status = dependencies.host.status.getPluginStatus(plugin);
    const needsInstallBadge = status === PLUGIN_STATUS_BACKEND_NOT_INSTALLED || status === PLUGIN_STATUS_INSTALL_ERROR ? `<div class="plugin-install-badge" data-state="needs-install">${i18n.t('plugins.modal.installBackend.needsInstall')}</div>` : '';

    const infoMarkup = toTrustedUiHtml(`
        <div class="plugin-info-item">
        <div class="plugin-info-content">
        <div class="plugin-info-name">
        <span id="${ledId}" class="status-indicator plugin-info-led"></span>
        <span data-tooltip="${esc(name)}">${esc(name)} ${i18n.t('plugins.modal.manageBackend.pluginSuffix')}</span>
        </div>
        ${backendVersion ? `<div class="plugin-info-details"><span class="plugin-info-version plugin-backend-version">${i18n.t('plugins.modal.manageBackend.backend_version', { version: esc(backendVersion) })}</span></div>` : ''}
        <div class="plugin-info-details"><span class="plugin-info-version">${i18n.t('plugins.modal.manageBackend.pluginVersion', { version: esc(pluginVersion) })}</span><span class="plugin-info-author">${i18n.t('plugins.modal.manageBackend.author', { author: esc(author) })}</span></div>
        <div class="plugin-info-details"><span class="plugin-info-status">${i18n.t('plugins.modal.manageBackend.backendStatus', { status: esc(backendStatus) })}</span></div>
        ${buildBackendWebsiteLink(websiteLinkId, getBackendWebsiteUrl(plugin), dependencies.security)}
        </div>
        ${needsInstallBadge}
        </div>`);
    dependencies.host.view.updateHTML(info, infoMarkup, { escape: false });

    const linkElement = dependencies.host.view.optionalHTMLElement(modalUiSelector(modalId, 'website-link'), info);
    if (linkElement) {
        bindBackendWebsiteLinkClick(dependencies.host, linkElement);
    }
    const led = dependencies.host.view.optionalHTMLElement(modalUiSelector(modalId, 'info-led'), info);
    const statusManager = dependencies.host.status.getStatusManager();
    if (led && statusManager) {
        statusManager.updateIndicator(led, dependencies.host.status.getPluginStatus(plugin));
    }
};

const renderManageBackendWarning = (dependencies: ManageInfoViewDependencies & { classNames: ManageClassNames }, modalId: string, modalRoot: HTMLElement, plugin: PluginRecord): void => {
    const warning = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'warning'), modalRoot);
    const messages = getPluginSystemRequirementMessages(plugin, 'install_backend');
    dependencies.host.view.toggleClassName(warning, dependencies.classNames.hidden, messages.length === 0);
    if (!messages.length) {
        warning.replaceChildren();
        return;
    }
    const markup = toTrustedUiHtml(messages.map((message) => `<span>${dependencies.security.escapeHtml(message)}</span>`).join('<br>'));
    dependencies.host.view.updateHTML(warning, markup, { escape: false });
};

const resetManageBackendButtons = (dependencies: ManageButtonsViewDependencies, modalId: string, modalRoot: HTMLElement): void => {
    const checkBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'check-update'), modalRoot);
    dependencies.host.view.updateText(checkBtn, i18n.t('plugins.modal.manageBackend.checkUpdates'));
    checkBtn.className = 'ui-button ui-variant-primary backend-check-button';
    setElementDisabledState(dependencies.host.view, checkBtn, false, dependencies.classNames.disabled);
    dependencies.host.view.setDataAttribute(checkBtn, 'mode', 'check');

    const uninstallBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'uninstall'), modalRoot);
    setElementDisabledState(dependencies.host.view, uninstallBtn, false, dependencies.classNames.disabled);
    const startBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'start-install'), modalRoot);
    setElementDisabledState(dependencies.host.view, startBtn, false, dependencies.classNames.disabled);

    const versionInfo = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'version-info'), modalRoot);
    dependencies.host.view.addClassName(versionInfo, dependencies.classNames.hidden);
    versionInfo.replaceChildren();
};

const canManageBackend = (dependencies: ManageButtonsViewDependencies, plugin: PluginRecord): boolean => {
    const status = dependencies.host.status.getPluginStatus(plugin);
    return status !== PLUGIN_STATUS_BACKEND_NOT_INSTALLED && status !== PLUGIN_STATUS_INSTALL_ERROR && status !== PLUGIN_STATUS_BACKEND_INSTALLING && status !== PLUGIN_STATUS_BACKEND_UPDATING;
};

const canInstallBackend = (dependencies: ManageButtonsViewDependencies, plugin: PluginRecord): boolean => {
    const status = dependencies.host.status.getPluginStatus(plugin);
    return status === PLUGIN_STATUS_BACKEND_NOT_INSTALLED || status === PLUGIN_STATUS_INSTALL_ERROR;
};

const syncManageBackendFooterActions = (dependencies: ManageButtonsViewDependencies, modalId: string, modalRoot: HTMLElement, plugin: PluginRecord | null): boolean => {
    const canManage = plugin ? canManageBackend(dependencies, plugin) : false;
    const canInstall = plugin ? canInstallBackend(dependencies, plugin) : false;
    const manageHidden = !canManage;
    const installHidden = !canInstall;
    const uninstallBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'uninstall'), modalRoot);
    const checkBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'check-update'), modalRoot);
    const startBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'start-install'), modalRoot);
    dependencies.host.view.toggleClassName(uninstallBtn, dependencies.classNames.hidden, manageHidden);
    dependencies.host.view.toggleClassName(checkBtn, dependencies.classNames.hidden, manageHidden);
    dependencies.host.view.toggleClassName(startBtn, dependencies.classNames.hidden, installHidden);
    setElementDisabledState(dependencies.host.view, uninstallBtn, manageHidden, dependencies.classNames.disabled);
    setElementDisabledState(dependencies.host.view, checkBtn, manageHidden, dependencies.classNames.disabled);
    setElementDisabledState(dependencies.host.view, startBtn, installHidden, dependencies.classNames.disabled);
    const selectorSlot = dependencies.host.view.optionalHTMLElement(modalUiSelector(modalId, 'variant-selector'), modalRoot);
    if (selectorSlot) {
        dependencies.host.view.toggleClassName(selectorSlot, dependencies.classNames.hidden, !canManage && !canInstall);
    }
    return canManage || canInstall;
};

const renderManageBackendUpdateInfo = (dependencies: ManageUpdateViewDependencies, modalId: string, modalRoot: HTMLElement, info: PluginBackendUpdateStatus | null, updateAvailable: boolean): void => {
    const versionInfo = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'version-info'), modalRoot);
    const currentPlugin = dependencies.state.currentPlugin;
    if (!currentPlugin) {
        throw new Error('Manage backend update info requires an active plugin');
    }

    const versionToNormalize = info?.currentVersion ?? currentPlugin.backendVersion;
    const current = dependencies.host.status.normalizeVersion(versionToNormalize);

    const infoContainer = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'plugin-info'), modalRoot);
    const backendVersionElement = dependencies.host.view.optionalHTMLElement('.plugin-backend-version', infoContainer);
    if (backendVersionElement && current.raw !== i18n.t('common.unknown')) {
        dependencies.host.view.updateText(backendVersionElement, i18n.t('plugins.modal.manageBackend.backend_version', { version: current.raw }));
    }

    if (updateAvailable) {
        const latest = dependencies.host.status.normalizeVersion(info?.latestVersion);
        const updateMarkup = toTrustedUiHtml(`<div class="form-group"><label>${i18n.t('plugins.modal.manageBackend.update_available')}</label>
                <div class="version-comparison">
                <div class="version-item"><span class="version-label">${i18n.t('plugins.modal.manageBackend.current_version')}</span><span class="version-value">${dependencies.security.escapeHtml(current.safe)}</span></div>
                <div class="version-arrow">→</div>
                <div class="version-item"><span class="version-label">${i18n.t('plugins.modal.manageBackend.newVersion')}</span><span class="version-value version-new">${dependencies.security.escapeHtml(latest.safe)}</span></div>
                </div></div>`);
        dependencies.host.view.updateHTML(versionInfo, updateMarkup, { escape: false });
    } else {
        const currentVersionMarkup = toTrustedUiHtml(`<div class="form-group"><label>${i18n.t('plugins.modal.manageBackend.upToDate')}</label>
                <div class="version-comparison">
                <div class="version-item"><span class="version-label">${i18n.t('plugins.modal.manageBackend.currentVersionLabel')}</span><span class="version-value">${dependencies.security.escapeHtml(current.safe)}</span></div>
                </div></div>`);
        dependencies.host.view.updateHTML(versionInfo, currentVersionMarkup, { escape: false });
    }

    dependencies.host.view.removeClassName(versionInfo, dependencies.classNames.hidden);
};

const showManageBackendUpdateAvailable = (dependencies: ManageUpdateViewDependencies, modalId: string, modalRoot: HTMLElement, info: PluginBackendUpdateStatus): void => {
    renderManageBackendUpdateInfo(dependencies, modalId, modalRoot, info, true);
    const checkBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'check-update'), modalRoot);
    dependencies.host.view.updateText(checkBtn, i18n.t('plugins.modal.manageBackend.update'));
    checkBtn.className = 'ui-button ui-variant-accent';
    dependencies.host.view.setDataAttribute(checkBtn, 'mode', 'update');
};

const showManageBackendNoUpdateAvailable = (dependencies: ManageUpdateViewDependencies, modalId: string, modalRoot: HTMLElement): void => {
    renderManageBackendUpdateInfo(dependencies, modalId, modalRoot, dependencies.state.updateInfo, false);
};

const hideManageBackendUpdateControls = (dependencies: ManageButtonsViewDependencies, modalId: string, modalRoot: HTMLElement): void => {
    const checkBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'check-update'), modalRoot);
    dependencies.host.view.addClassName(checkBtn, dependencies.classNames.hidden);
    setElementDisabledState(dependencies.host.view, checkBtn, true, dependencies.classNames.disabled);
    const selectorSlot = dependencies.host.view.optionalHTMLElement(modalUiSelector(modalId, 'variant-selector'), modalRoot);
    if (selectorSlot) {
        dependencies.host.view.addClassName(selectorSlot, dependencies.classNames.hidden);
    }
    const versionInfo = dependencies.host.view.optionalHTMLElement(modalUiSelector(modalId, 'version-info'), modalRoot);
    if (versionInfo) {
        dependencies.host.view.addClassName(versionInfo, dependencies.classNames.hidden);
        versionInfo.replaceChildren();
    }
};

const setManageBackendButtonsDisabled = (dependencies: ManageButtonsViewDependencies, modalId: string, modalRoot: HTMLElement, disabled: boolean): void => {
    const checkBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'check-update'), modalRoot);
    const uninstallBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'uninstall'), modalRoot);
    const startBtn = dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'start-install'), modalRoot);
    setElementDisabledState(dependencies.host.view, checkBtn, disabled, dependencies.classNames.disabled);
    setElementDisabledState(dependencies.host.view, uninstallBtn, disabled, dependencies.classNames.disabled);
    setElementDisabledState(dependencies.host.view, startBtn, disabled, dependencies.classNames.disabled);
    setBackendVariantSelectorDisabled(dependencies.host, modalId, modalRoot, disabled);
};

const clearManageBackendModalView = (dependencies: ManageButtonsViewDependencies, modalId: string, modalRoot: HTMLElement): void => {
    const infoContainer = dependencies.host.view.optionalHTMLElement(modalUiSelector(modalId, 'plugin-info'), modalRoot);
    if (infoContainer) {
        infoContainer.replaceChildren();
    }
    const versionInfo = dependencies.host.view.optionalHTMLElement(modalUiSelector(modalId, 'version-info'), modalRoot);
    if (versionInfo) {
        dependencies.host.view.addClassName(versionInfo, dependencies.classNames.hidden);
        versionInfo.replaceChildren();
    }
    const warning = dependencies.host.view.optionalHTMLElement(modalUiSelector(modalId, 'warning'), modalRoot);
    if (warning) {
        dependencies.host.view.addClassName(warning, dependencies.classNames.hidden);
        warning.replaceChildren();
    }
    const operationContainer = dependencies.host.view.optionalHTMLElement(modalUiSelector(modalId, 'operation-container'), modalRoot);
    if (operationContainer) {
        operationContainer.replaceChildren();
    }
};

export { clearManageBackendModalView, hideManageBackendUpdateControls, renderManageBackendInfo, renderManageBackendWarning, resetManageBackendButtons, setManageBackendButtonsDisabled, showManageBackendNoUpdateAvailable, showManageBackendUpdateAvailable, syncManageBackendFooterActions };
