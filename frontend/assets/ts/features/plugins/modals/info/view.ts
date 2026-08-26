/* SoAI - Plugins feature info rendering [frontend/assets/ts/features/plugins/modals/info/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isCircuitBreakerStateActive, requireActiveCircuitBreakerNumber } from '@core/plugins/circuitBreaker.ts';
import { resolvePluginModelRepositoryUrl } from '@core/plugins/modelRepositoryContract.ts';
import { formatDateTimeWithOptions } from '@core/primitives/dateTime.ts';
import { isArray, isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import type { InfoManagerHost, PluginCapabilityDescriptor, SecurityService } from '@features/plugins/modals/info/types.ts';

interface PluginInfoRenderContext {
    host: InfoManagerHost;
    security: SecurityService;
}
const formatPluginInfoTimestamp = (timestamp: number, security: SecurityService): string => {
    if (!timestamp) {
        return '';
    }
    try {
        return formatDateTimeWithOptions(timestamp, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (error) {
        errorHandler.warn('PluginInfoModal', 'Failed to format plugin timestamp', ensureError(error));
        return security.escapeHtml(String(timestamp));
    }
};
const renderBasicInfoSection = (plugin: PluginRecord, context: PluginInfoRenderContext): string => {
    const { security } = context;
    const name = security.escapeHtml((plugin.displayName || plugin.name) ?? '');
    const version = security.escapeHtml(plugin.versionSoaiplugin ?? '');
    const author = security.escapeHtml(plugin.authorSoaiplugin ?? '');
    const description = security.escapeHtml(plugin.descriptionSoaiplugin ?? '');
    const licenseSoaiplugin = security.escapeHtml(plugin.licenseSoaiplugin ?? '');
    const licenseManagedBackend = security.escapeHtml(plugin.licenseManagedBackend ?? '');

    return `
                <div class="plugin-info-section">
                    <div class="plugin-info-header">
                        <h3 class="plugin-info-title">${name}<span class="plugin-info-title-suffix">${i18n.t('plugins.modal.info.titleSuffix')}</span></h3>
                        <span class="plugin-info-version">${version}</span>
                    </div>
                    ${author ? `<div class="plugin-info-row"><span class="plugin-info-label">${i18n.t('plugins.modal.info.author')}</span><span class="plugin-info-value">${author}</span></div>` : ''}
                    ${licenseSoaiplugin ? `<div class="plugin-info-row"><span class="plugin-info-label">${i18n.t('plugins.modal.info.license_soaiplugin')}</span><span class="plugin-info-value">${licenseSoaiplugin}</span></div>` : ''}
                    ${licenseManagedBackend ? `<div class="plugin-info-row"><span class="plugin-info-label">${i18n.t('plugins.modal.info.license_managed_backend')}</span><span class="plugin-info-value">${licenseManagedBackend}</span></div>` : ''}
                    ${description ? `<p class="plugin-info-description">${description}</p>` : ''}
                </div>
            `;
};
const renderLinksSection = (plugin: PluginRecord, context: PluginInfoRenderContext): string => {
    const { security } = context;
    const links: string[] = [];
    const externalLinkIcon = renderIconSlot(getIconSync('external-link', { size: 14, strokeWidth: 1.5 }), { className: 'plugin-info-link-icon' });

    if (plugin.websiteSoaiplugin) {
        const safeUrl = security.resolveHttpsWebsiteUrl(plugin.websiteSoaiplugin);
        if (safeUrl) {
            const urlAttr = security.escapeAttribute(safeUrl);
            links.push(`<a href="${urlAttr}" target="_blank" rel="noopener noreferrer" class="plugin-info-link external-link-confirmation">${i18n.t('plugins.modal.info.website_soaiplugin')}${externalLinkIcon}</a>`);
        }
    }

    if (plugin.websiteBackend) {
        const safeUrl = security.resolveHttpsWebsiteUrl(plugin.websiteBackend);
        if (safeUrl) {
            const urlAttr = security.escapeAttribute(safeUrl);
            links.push(`<a href="${urlAttr}" target="_blank" rel="noopener noreferrer" class="plugin-info-link external-link-confirmation">${i18n.t('plugins.modal.info.website_backend')}${externalLinkIcon}</a>`);
        }
    }

    const modelRepositoryUrl = resolvePluginModelRepositoryUrl(plugin.modelRepository);
    if (modelRepositoryUrl) {
        const safeUrl = security.resolveHttpsWebsiteUrl(modelRepositoryUrl);
        if (safeUrl) {
            const urlAttr = security.escapeAttribute(safeUrl);
            links.push(`<a href="${urlAttr}" target="_blank" rel="noopener noreferrer" class="plugin-info-link external-link-confirmation">${i18n.t('plugins.modal.info.model_repository')}${externalLinkIcon}</a>`);
        }
    }

    if (!links.length) {
        return '';
    }

    return `
                <div class="plugin-info-section">
                    <h4 class="plugin-info-section-title">${i18n.t('plugins.modal.info.links')}</h4>
                    <div class="plugin-info-links">
                        ${links.join('')}
                    </div>
                </div>
            `;
};
const renderModelTypeBadges = (plugin: PluginRecord, context: PluginInfoRenderContext): string => {
    const { host } = context;
    const types = isArray(plugin?.modelTypes) ? plugin.modelTypes : [];
    const badges = types
        .map((entry: JsonValue) => {
            if (!isString(entry)) {
                return '';
            }
            const label = entry.trim();
            if (!label) {
                return '';
            }
            const formatted = host.sanitizeText(label.toUpperCase(), { allowEmpty: true });
            const badgeClass = getBadgeColorClass(label);
            return `<span class="ui-model-type-badge ${badgeClass}">${formatted}</span>`;
        })
        .filter(Boolean)
        .join('');
    return badges ? `<div class="ui-model-type-badges ui-model-type-badges--inline">${badges}</div>` : '';
};
const renderCapabilityBadges = (descriptors: readonly PluginCapabilityDescriptor[], context: PluginInfoRenderContext): string => {
    const { host, security } = context;
    if (!descriptors.length) {
        return '';
    }
    const badges = descriptors
        .map((descriptor: PluginCapabilityDescriptor) => {
            const label = host.sanitizeText(descriptor.label, { allowEmpty: true });
            if (!label) {
                return '';
            }
            const className = host.sanitizeClassName(descriptor.className, 'capability');
            const colorClass = getBadgeColorClass(descriptor.id || label);
            const title = descriptor.title ? security.escapeAttribute(descriptor.title) : '';
            const tooltipAttr = title ? ` data-tooltip="${title}"` : '';
            return `<span class="ui-model-type-badge capability-badge ${className} ${colorClass}"${tooltipAttr}>${label}</span>`;
        })
        .filter(Boolean)
        .join('');
    return badges ? `<div class="ui-model-type-badges ui-model-type-badges--inline capability-badges">${badges}</div>` : '';
};
const renderBadgesSection = (plugin: PluginRecord, context: PluginInfoRenderContext, capabilityDescriptors: readonly PluginCapabilityDescriptor[]): string => {
    const modelTypeBadges = renderModelTypeBadges(plugin, context);
    const capabilityBadges = renderCapabilityBadges(capabilityDescriptors, context);

    if (!modelTypeBadges && !capabilityBadges) {
        return '';
    }

    return `
                <div class="plugin-info-section">
                    <h4 class="plugin-info-section-title">${i18n.t('plugins.modal.info.capabilities')}</h4>
                    <div class="plugin-info-badges">
                        ${modelTypeBadges}
                        ${capabilityBadges}
                    </div>
                </div>
            `;
};
const renderStateSection = (plugin: PluginRecord, context: PluginInfoRenderContext): string => {
    const { security } = context;
    const state = security.escapeHtml(plugin.state ?? '');
    const isBuiltin = plugin.isBuiltin ? i18n.t('common.yes') : i18n.t('common.no');
    const isPersistent = plugin.isPersistent ? i18n.t('common.yes') : i18n.t('common.no');
    const isEnabled = plugin.isEnabled ? i18n.t('common.yes') : i18n.t('common.no');
    const coreCompat = security.escapeHtml(plugin.coreCompat ?? '');

    const modalities = isArray(plugin.modalities) ? plugin.modalities : [];
    const modalitiesHtml = modalities.length ? security.escapeHtml(modalities.join(', ')) : i18n.t('common.none');

    return `
                <div class="plugin-info-section">
                    <h4 class="plugin-info-section-title">${i18n.t('plugins.modal.info.status')}</h4>
                    <div class="plugin-info-grid">
                        <div class="plugin-info-row">
                            <span class="plugin-info-label">${i18n.t('plugins.modal.info.state')}</span>
                            <span class="plugin-info-value">${state}</span>
                        </div>
                        <div class="plugin-info-row">
                            <span class="plugin-info-label">${i18n.t('plugins.modal.info.builtin')}</span>
                            <span class="plugin-info-value">${isBuiltin}</span>
                        </div>
                        <div class="plugin-info-row">
                            <span class="plugin-info-label">${i18n.t('plugins.modal.info.persistent')}</span>
                            <span class="plugin-info-value">${isPersistent}</span>
                        </div>
                        <div class="plugin-info-row">
                            <span class="plugin-info-label">${i18n.t('plugins.modal.info.enabled')}</span>
                            <span class="plugin-info-value">${isEnabled}</span>
                        </div>
                        <div class="plugin-info-row">
                            <span class="plugin-info-label">${i18n.t('plugins.modal.info.core_compat')}</span>
                            <span class="plugin-info-value">${coreCompat}</span>
                        </div>
                        <div class="plugin-info-row">
                            <span class="plugin-info-label">${i18n.t('plugins.modal.info.modalities')}</span>
                            <span class="plugin-info-value">${modalitiesHtml}</span>
                        </div>
                    </div>
                </div>
            `;
};
const renderTechnicalSection = (plugin: PluginRecord, context: PluginInfoRenderContext): string => {
    const { security } = context;
    const technical = isObject(plugin.technical) ? plugin.technical : null;
    const filePath = security.escapeHtml(String(technical?.filePath ?? ''));
    const fileHash = security.escapeHtml(String(technical?.fileHash ?? ''));
    const maxConcurrent = security.escapeHtml(String(technical?.maxConcurrentRequests ?? ''));
    const firstSeenAtMs = technical?.firstSeenAtMs;
    const firstSeen = typeof firstSeenAtMs === 'number' && firstSeenAtMs > 0 ? formatPluginInfoTimestamp(firstSeenAtMs, security) : '';
    const lastSeenAtMs = technical?.lastSeenAtMs;
    const lastSeen = typeof lastSeenAtMs === 'number' && lastSeenAtMs > 0 ? formatPluginInfoTimestamp(lastSeenAtMs, security) : '';

    return `
                <div class="plugin-info-section">
                    <h4 class="plugin-info-section-title">${i18n.t('plugins.modal.info.technical')}</h4>
                    <div class="plugin-info-grid">
                        ${filePath ? `<div class="plugin-info-row plugin-info-row-full"><span class="plugin-info-label">${i18n.t('plugins.modal.info.file_path')}</span><span class="plugin-info-value plugin-info-value-mono">${filePath}</span></div>` : ''}
                        ${fileHash ? `<div class="plugin-info-row plugin-info-row-full"><span class="plugin-info-label">${i18n.t('plugins.modal.info.file_hash')}</span><span class="plugin-info-value plugin-info-value-mono">${fileHash}</span></div>` : ''}
                        ${maxConcurrent ? `<div class="plugin-info-row"><span class="plugin-info-label">${i18n.t('plugins.modal.info.maxConcurrent')}</span><span class="plugin-info-value">${maxConcurrent}</span></div>` : ''}
                        ${firstSeen ? `<div class="plugin-info-row"><span class="plugin-info-label">${i18n.t('plugins.modal.info.firstSeen')}</span><span class="plugin-info-value">${firstSeen}</span></div>` : ''}
                        ${lastSeen ? `<div class="plugin-info-row"><span class="plugin-info-label">${i18n.t('plugins.modal.info.last_seen')}</span><span class="plugin-info-value">${lastSeen}</span></div>` : ''}
                    </div>
                </div>
            `;
};
const renderCircuitBreakerSection = (plugin: PluginRecord, context: PluginInfoRenderContext): string => {
    const { security } = context;
    const breaker = plugin.circuitBreaker && isObject(plugin.circuitBreaker) ? plugin.circuitBreaker : null;
    const state = security.escapeHtml(String(breaker?.['state'] ?? ''));
    const isOpen = breaker?.isOpen === true ? i18n.t('common.yes') : i18n.t('common.no');
    const breakerActive = isCircuitBreakerStateActive(breaker?.['state'], breaker?.isOpen);
    const failureCountValue = breaker?.failureCount;
    const thresholdValue = breaker?.failureThreshold;
    const timeoutValue = breaker?.recoveryTimeoutSec;
    if (breakerActive) requireActiveCircuitBreakerNumber(failureCountValue, 'failure_count');
    if (breakerActive) requireActiveCircuitBreakerNumber(thresholdValue, 'failure_threshold');
    if (breakerActive) requireActiveCircuitBreakerNumber(timeoutValue, 'recovery_timeout_sec');
    const failureCount = security.escapeHtml(String(isFiniteNumber(failureCountValue) ? failureCountValue : 0));
    const threshold = security.escapeHtml(String(isFiniteNumber(thresholdValue) ? thresholdValue : 0));
    const timeout = security.escapeHtml(String(isFiniteNumber(timeoutValue) ? timeoutValue : 0));
    const lastFailureValue = breaker?.lastFailureAtMs;
    const lastFailure = typeof lastFailureValue === 'number' && lastFailureValue > 0 ? formatPluginInfoTimestamp(lastFailureValue, security) : '';

    return `
                <div class="plugin-info-section">
                    <h4 class="plugin-info-section-title">${i18n.t('plugins.modal.info.circuit_breaker')}</h4>
                    <div class="plugin-info-grid">
                        <div class="plugin-info-row">
                            <span class="plugin-info-label">${i18n.t('plugins.modal.info.cbState')}</span>
                            <span class="plugin-info-value">${state}</span>
                        </div>
                        <div class="plugin-info-row">
                            <span class="plugin-info-label">${i18n.t('plugins.modal.info.cbOpen')}</span>
                            <span class="plugin-info-value">${isOpen}</span>
                        </div>
                        <div class="plugin-info-row">
                            <span class="plugin-info-label">${i18n.t('plugins.modal.info.cbFailures')}</span>
                            <span class="plugin-info-value">${failureCount} / ${threshold}</span>
                        </div>
                        <div class="plugin-info-row">
                            <span class="plugin-info-label">${i18n.t('plugins.modal.info.cbTimeout')}</span>
                            <span class="plugin-info-value">${timeout}s</span>
                        </div>
                        ${lastFailure ? `<div class="plugin-info-row"><span class="plugin-info-label">${i18n.t('plugins.modal.info.cbLastFailure')}</span><span class="plugin-info-value">${lastFailure}</span></div>` : ''}
                    </div>
                </div>
            `;
};
const renderPluginInfoHtml = (plugin: PluginRecord, context: PluginInfoRenderContext, capabilityDescriptors: readonly PluginCapabilityDescriptor[]): TrustedHtml => {
    const sections: string[] = [];
    sections.push(renderBasicInfoSection(plugin, context));
    sections.push(renderBadgesSection(plugin, context, capabilityDescriptors));
    sections.push(renderLinksSection(plugin, context));
    sections.push(renderStateSection(plugin, context));
    sections.push(renderTechnicalSection(plugin, context));
    sections.push(renderCircuitBreakerSection(plugin, context));

    return toTrustedUiHtml(sections.filter(Boolean).join(''));
};

export { renderPluginInfoHtml };
