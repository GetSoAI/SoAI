/* SoAI - Plugins page rendering layer card renderer implementation [frontend/assets/ts/pages/plugins/rendering/cardrenderer/rendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { MODELS_ACTION_ADD_PROVIDER, MODELS_ACTION_DOWNLOAD_MODEL } from '@core/models/pageActions.ts';
import { renderActionToggleSwitch } from '@core/toggleSwitch.ts';
import { PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_BACKEND_UPDATING, PLUGIN_STATUS_DELETE_ERROR, PLUGIN_STATUS_INSTALL_ERROR, PLUGIN_STATUS_LOAD_ERROR, PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR, PLUGIN_STATUS_UPDATE_ERROR } from '@core/state/pluginStatus.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { PROVIDER_MODE, resolveProviderMode } from '@features/catalog/public.ts';
import { PLUGINS_ACTION_INSTALL_BACKEND, PLUGINS_ACTION_METRIC_BADGE, PLUGINS_ACTION_TOGGLE_ENABLED } from '@features/plugins/public.ts';
import type { PluginCardHost } from '@pages/plugins/rendering/cardrenderer/types.ts';

interface BackendStatuses {
    backendNotInstalled: string;
    backendInstalling: string;
}

interface PluginEnabledToggleOptions {
    permanentlyDisabled: boolean;
    circuitBreakerActive: boolean;
    locked: boolean;
    checked: boolean;
    available: boolean;
    pendingToggleTarget: boolean | null;
    disabledClassName: string;
    label: string;
    showLabel: boolean;
}

function resolveToggleLabelText(permanentlyDisabled: boolean, quarantined: boolean, overrideRequired: boolean, overrideActive: boolean, toggleChecked: boolean): string {
    if (quarantined) {
        return i18n.t('plugins.status.quarantined');
    }
    if (permanentlyDisabled) {
        return i18n.t('plugins.status.incompatible');
    }
    if (overrideActive) {
        return i18n.t('plugins.status.overrideActive');
    }
    if (overrideRequired) {
        return i18n.t('plugins.status.overrideRequired');
    }
    if (toggleChecked) {
        return i18n.t('plugins.status.enabled');
    }
    return i18n.t('plugins.status.disabled');
}

function buildPluginEnabledToggle(options: PluginEnabledToggleOptions): string {
    const pending = options.pendingToggleTarget === true || options.pendingToggleTarget === false;
    const inputClasses = ['plugin-enable-checkbox'];
    if (options.permanentlyDisabled || options.locked || !options.available || pending) {
        inputClasses.push(options.disabledClassName);
    }
    const wrapperDataset: Record<string, string> = {};
    if (options.circuitBreakerActive) {
        wrapperDataset['resetTarget'] = 'circuit-breaker';
    }
    return renderActionToggleSwitch({
        action: PLUGINS_ACTION_TOGGLE_ENABLED,
        checked: options.checked,
        label: options.label,
        wrapperTag: 'div',
        wrapperClassName: 'plugin-enable-toggle ui-collection-card__toggle',
        inputClassName: inputClasses.join(' '),
        labelClassName: 'plugin-enable-label ui-collection-card__toggle-label toggle-label',
        labelMode: options.showLabel ? 'visible' : 'omitted',
        pending,
        locked: options.locked,
        wrapperDataset
    });
}

function getBackendStatus(plugin: PluginRecord, host: PluginCardHost): string {
    return host.status.getBackendStatus(plugin);
}

function getBackendBadgeValue(plugin: PluginRecord, host: PluginCardHost): string {
    if (host.compatibility.isPluginPermanentlyDisabled(plugin)) {
        return getBackendStatus(plugin, host);
    }
    const status = host.status.getPluginStatus(plugin);
    if (status === PLUGIN_STATUS_BACKEND_NOT_INSTALLED) {
        const availableCount = host.status.getBackendAvailableVariantCount(plugin);
        return availableCount === null ? getBackendStatus(plugin, host) : i18n.t('plugins.badges.availableBackends', { count: availableCount });
    }
    return i18n.t('plugins.badges.manageBackend');
}

function renderSecondBadge(plugin: PluginRecord, backendStatusAttr: string, host: PluginCardHost): string {
    const capabilities = isObject(plugin.capabilities) ? plugin.capabilities : {};
    const providerMode = resolveProviderMode(plugin);

    if (providerMode !== PROVIDER_MODE.NONE && capabilities.supportsBackendInstallation === false) {
        const isManaged = providerMode === PROVIDER_MODE.USER_MANAGED;
        const value = isManaged ? plugin.stats?.providerCount || 0 : i18n.t('plugins.providerMode.badges.pluginManaged');
        const tooltipText = isManaged ? i18n.t('plugins.providerMode.tooltips.userManaged') : i18n.t('plugins.providerMode.tooltips.pluginManaged');
        const tooltip = host.presentation.sanitizeText(tooltipText);
        const labelAttributes = isManaged ? ` ${renderLabelAttributes(tooltipText)}` : tooltip ? ` data-tooltip="${tooltip}"` : '';

        const attrs = [isManaged ? `data-action="${PLUGINS_ACTION_METRIC_BADGE}"` : '', 'data-metric-key="providers"', `data-provider-mode="${providerMode}"`].filter(Boolean).join(' ');

        const tagName = isManaged ? 'button' : 'div';
        const typeAttribute = isManaged ? ' type="button"' : '';
        return `<div class="ui-metric-item"><${tagName}${typeAttribute} class="ui-metric-badge ui-metric-badge--secondary" ${attrs}${labelAttributes}><span class="ui-metric-label">${i18n.t('plugins.badges.providers')}</span><span class="ui-metric-value">${host.presentation.sanitizeText(String(value), { allowEmpty: true })}</span></${tagName}></div>`;
    }

    if (capabilities.supportsBackendInstallation !== false) {
        const backendAttr = backendStatusAttr ? ` ${backendStatusAttr}` : '';
        const backendLabel = i18n.t('plugins.badges.backend');
        return `<div class="ui-metric-item"><button type="button" class="ui-metric-badge ui-metric-badge--secondary" data-action="${PLUGINS_ACTION_METRIC_BADGE}" data-metric-key="backend"${backendAttr} ${renderLabelAttributes(backendLabel)}><span class="ui-metric-label">${backendLabel}</span><span class="ui-metric-value">${getBackendBadgeValue(plugin, host)}</span></button></div>`;
    }

    const requestsLabel = i18n.t('plugins.badges.requests');
    return `<div class="ui-metric-item"><button type="button" class="ui-metric-badge ui-metric-badge--secondary" data-action="${PLUGINS_ACTION_METRIC_BADGE}" data-metric-key="requests" ${renderLabelAttributes(requestsLabel)}><span class="ui-metric-label">${requestsLabel}</span><span class="ui-metric-value">${plugin.technical?.maxConcurrentRequests || 0}</span></button></div>`;
}

function renderInstallButton(plugin: PluginRecord, host: PluginCardHost, statuses: { backendNotInstalled: string }): string {
    if (host.compatibility.requiresCompatibilityOverride(plugin)) {
        return '';
    }
    const capabilities = isObject(plugin.capabilities) ? plugin.capabilities : {};
    const status = host.status.getPluginStatus(plugin);
    if (host.compatibility.isPluginPermanentlyDisabled(plugin) || (status !== statuses.backendNotInstalled && status !== PLUGIN_STATUS_INSTALL_ERROR) || capabilities.supportsBackendInstallation === false) {
        return '';
    }
    const label = i18n.t('plugins.actions.installBackend');
    const icon = renderIconSlot(getIconSync('download', { size: 12, strokeWidth: 1.5 }));
    return `<button type="button" class="ui-button ui-button--sm ui-variant-accent status-install-button" data-action="${PLUGINS_ACTION_INSTALL_BACKEND}" ${renderLabelAttributes(label)}>${icon}<span>${label}</span></button>`;
}

function renderDownloadModelButton(plugin: PluginRecord, host: PluginCardHost, statuses: BackendStatuses): string {
    if (host.compatibility.isPluginPermanentlyDisabled(plugin) || host.compatibility.requiresCompatibilityOverride(plugin)) {
        return '';
    }

    const status = host.status.getPluginStatus(plugin);
    const capabilities = isObject(plugin.capabilities) ? plugin.capabilities : {};
    const providerMode = resolveProviderMode(plugin);
    const supportsDownload = capabilities.supportsModelDownload === true;
    const isUserManagedProvider = providerMode === PROVIDER_MODE.USER_MANAGED;
    const modelCount = plugin.stats?.modelCount || 0;
    const localBackendUnavailable = [statuses.backendNotInstalled, statuses.backendInstalling, PLUGIN_STATUS_BACKEND_UPDATING, PLUGIN_STATUS_INSTALL_ERROR, PLUGIN_STATUS_LOAD_ERROR, PLUGIN_STATUS_UPDATE_ERROR, PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR, PLUGIN_STATUS_DELETE_ERROR].includes(status);

    const actions: string[] = [];
    if (isUserManagedProvider) {
        if (!localBackendUnavailable && modelCount === 0) {
            const label = i18n.t('plugins.actions.addProvider');
            const icon = renderIconSlot(getIconSync('provider', { size: 12, strokeWidth: 1.5 }));
            actions.push(`<button type="button" class="ui-button ui-button--sm ui-variant-accent status-install-button" data-action="${MODELS_ACTION_ADD_PROVIDER}" ${renderLabelAttributes(label)}>${icon}<span>${label}</span></button>`);
        }
    } else if (supportsDownload && !localBackendUnavailable && modelCount === 0) {
        const label = i18n.t('plugins.actions.downloadModel');
        const icon = renderIconSlot(getIconSync('download', { size: 12, strokeWidth: 1.5 }));
        actions.push(`<button type="button" class="ui-button ui-button--sm ui-variant-accent status-install-button" data-action="${MODELS_ACTION_DOWNLOAD_MODEL}" ${renderLabelAttributes(label)}>${icon}<span>${label}</span></button>`);
    }
    if (actions.length === 0) {
        return '';
    }
    return actions.join('');
}

function renderModelTypeBadges(plugin: PluginRecord): string {
    const types = isArray(plugin?.modelTypes) ? plugin.modelTypes : [];
    const badges = types
        .map((entry) => {
            if (!isString(entry)) return '';
            const label = entry.trim();
            if (!label) return '';
            return `<span class="ui-model-type-badge ${getBadgeColorClass(label)}">${label.toUpperCase()}</span>`;
        })
        .filter(Boolean)
        .join('');
    return badges ? `<div class="ui-model-type-badges ui-model-type-badges--inline">${badges}</div>` : '';
}

export { resolveToggleLabelText, buildPluginEnabledToggle, renderSecondBadge, renderInstallButton, renderDownloadModelButton, renderModelTypeBadges };
