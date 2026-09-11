/* SoAI - Plugins page card renderer rendering [frontend/assets/ts/pages/plugins/rendering/cardrenderer/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderRecentItemBadge } from '@core/collectionpage/recentItemTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/labelAttributes.ts';
import { isPluginModelUnavailableStatus } from '@core/state/pluginStatus.ts';
import { PLUGINS_ACTION_METRIC_BADGE } from '@features/plugins/public.ts';
import { buildPluginEnabledToggle, renderDownloadModelButton, renderInstallButton, renderModelTypeBadges, renderSecondBadge, resolveToggleLabelText } from '@pages/plugins/rendering/cardrenderer/rendering.ts';
import { resolveToggleChecked } from '@pages/plugins/rendering/cardrenderer/pluginCardToggleStateWidget.ts';
import type { PluginCardHost, RenderCardContentDependencies } from '@pages/plugins/rendering/cardrenderer/types.ts';

function buildStatusClassAttribute(host: PluginCardHost, status: string): string {
    const statusClass = isPluginModelUnavailableStatus(status) ? host.sanitizeClassName(status, 'status') : '';
    return statusClass ? `data-status="${statusClass}"` : '';
}

function renderCardContent(dependencies: RenderCardContentDependencies): string {
    const { plugin, data, host, constants } = dependencies;
    const sanitize = (value: string): string => host.presentation.sanitizeText(value);
    const status = host.status.getPluginStatus(plugin);
    const pendingToggleTarget = host.actions.getPendingToggleTarget(plugin);
    const permanentlyDisabled = host.compatibility.isPluginPermanentlyDisabled(plugin);
    const hardwareIncompatible = data.hardwareIncompatible === true;
    const circuitBreakerActive = data.circuitBreakerActive;
    const quarantined = circuitBreakerActive || data.status === constants.statuses.quarantined;
    const quarantineLocked = quarantined && !circuitBreakerActive;

    const overrideRequired = data.overrideRequired;
    const toggleLocked = permanentlyDisabled || (!hardwareIncompatible && data.overrideRequired) || quarantineLocked;
    const compatibility = host.compatibility.getPluginCompatibility(plugin);
    const overrideActive = Boolean(compatibility?.isOverridden);
    const forceToggleUnchecked = toggleLocked || hardwareIncompatible || circuitBreakerActive;
    const toggleChecked = resolveToggleChecked(plugin.isEnabled, plugin.state, forceToggleUnchecked, pendingToggleTarget);
    const toggleLabel = resolveToggleLabelText(permanentlyDisabled, quarantined, overrideRequired, overrideActive, toggleChecked);
    const unknownLabel = i18n.t('common.unknown');
    const safeName = sanitize(plugin.name || unknownLabel);
    const statusAttrValue = buildStatusClassAttribute(host, status);
    const metricStatusBadgeClass = data.statusBadgeClass ? `ui-metric-badge--${data.statusBadgeClass}` : '';
    const desc = plugin.descriptionSoaiplugin?.trim() ?? '';
    const hasDescription = desc.length > 0;
    const truncDesc = hasDescription && desc.length > 90 ? `${desc.slice(0, 87)}...` : desc;
    const descriptionClass = hasDescription ? 'ui-collection-card__subtitle plugin-description' : 'ui-collection-card__subtitle plugin-description plugin-description-empty';
    const descriptionAttributes = hasDescription ? renderLabelAttributes(desc) : 'aria-hidden="true"';
    const pluginTypeLabel = plugin.isBuiltin ? i18n.t('plugins.badges.builtin') : i18n.t('plugins.badges.thirdparty');
    const versionLabel = i18n.t('plugins.badges.version');
    const modelsLabel = i18n.t('plugins.badges.models');
    const newBadge = host.actions.isNewItem(plugin) ? renderRecentItemBadge((value) => sanitize(value)) : '';
    const pluginLogo = host.presentation.getPluginLogo(plugin);
    const pluginLogoFallback = host.presentation.getPluginLogoFallback(plugin);

    return `
        <div class="ui-collection-card__header plugin-card-header">
        <div class="ui-collection-card__title-bar plugin-title-bar">
        <div class="ui-collection-card__title plugin-title" data-full-title="${safeName}">
        ${pluginLogo ? `<img src="${sanitize(pluginLogo)}" data-plugin-logo-fallback="${sanitize(pluginLogoFallback)}" alt="${safeName}" class="plugin-logo-small" />` : ''}
        <span class="ui-collection-card__title-text plugin-title-text" data-tooltip="${safeName}">${sanitize(host.presentation.formatPluginName(plugin.name) || unknownLabel)}</span>
        ${newBadge}
        </div>
        </div>
        </div>
        <p class="${descriptionClass}" ${descriptionAttributes}>${sanitize(truncDesc)}</p>
        <div class="ui-collection-card__content plugin-card-content">
        <div class="plugin-info ui-collection-card__info">
        <div class="plugin-author ui-collection-card__identifier">
            <span class="plugin-author-label">${i18n.t('plugins.labels.authorPrefix')}</span>
            <span class="plugin-author-value">${sanitize(plugin.authorSoaiplugin || unknownLabel)}</span>
        </div>
            ${renderModelTypeBadges(plugin)}
            <div class="plugin-logo-name ui-collection-card__horizontal">
            ${buildPluginEnabledToggle({
                permanentlyDisabled: permanentlyDisabled,
                circuitBreakerActive,
                locked: toggleLocked,
                checked: toggleChecked,
                available: hardwareIncompatible ? true : plugin.isAvailable !== false,
                pendingToggleTarget,
                disabledClassName: constants.classNames.disabled,
                label: toggleLabel,
                showLabel: !(permanentlyDisabled && !circuitBreakerActive)
            })}
                </div>
                ${circuitBreakerActive ? host.presentation.getCircuitBreakerNotice(plugin) : host.presentation.getIncompatibleNotice(plugin)}
                </div>
                </div>
                <div class="ui-collection-card__body plugin-card-body">
                <div class="ui-collection-card__bottom plugin-card-bottom">
                <div class="ui-collection-card__metrics-grid plugin-metrics-display">
                <div class="ui-metric-item">
                <button type="button" class="ui-metric-badge ui-metric-badge--primary" data-action="${PLUGINS_ACTION_METRIC_BADGE}" data-metric-key="version" ${renderLabelAttributes(versionLabel)}>
                <span class="ui-metric-label">${versionLabel}</span>
                <span class="ui-metric-value">${sanitize(plugin.versionSoaiplugin || i18n.t('common.notAvailableShort'))}</span>
                </button>
                </div>
                ${renderSecondBadge(plugin, statusAttrValue, host)}
                <div class="ui-metric-item">
                <button type="button" class="ui-metric-badge ui-metric-badge--tertiary" data-action="${PLUGINS_ACTION_METRIC_BADGE}" data-metric-key="models" ${renderLabelAttributes(modelsLabel)}>
                <span class="ui-metric-label">${modelsLabel}</span>
                <span class="ui-metric-value">${plugin.stats?.modelCount || 0}</span>
                </button>
                </div>
                <div class="ui-metric-item">
                <div class="ui-metric-badge ui-metric-badge--quaternary">
                <span class="ui-metric-label">${i18n.t('plugins.badges.type')}</span>
                <span class="ui-metric-value">${pluginTypeLabel}</span>
                </div>
                </div>
                </div>
                <div class="ui-collection-card__status-grid plugin-metrics-status">
                <div class="ui-metric-item">
                <div class="ui-metric-badge ui-metric-badge--status-full ${metricStatusBadgeClass}" ${statusAttrValue}>
                <span class="ui-metric-value">${sanitize(permanentlyDisabled ? i18n.t('plugins.status.incompatible') : quarantined ? i18n.t('plugins.status.quarantined') : (data.statusLabel ?? ''))}</span>
                ${renderInstallButton(plugin, host, { backendNotInstalled: constants.statuses.backendNotInstalled })}
                ${renderDownloadModelButton(plugin, host, {
                    backendNotInstalled: constants.statuses.backendNotInstalled,
                    backendInstalling: constants.statuses.backendInstalling
                })}
                </div>
                </div>
                </div>
                </div>
                </div>`;
}

export { renderCardContent, buildStatusClassAttribute };
