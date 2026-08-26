/* SoAI - Models feature download modal effects [frontend/assets/ts/features/models/modals/downloadmodal/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { requireInputElement, requireSelectElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { getPluginSystemRequirementMessages } from '@core/plugins/systemRequirements.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { DownloadModalHost } from '@features/models/modals/downloadmodal/downloadModalTypes.ts';
import { buildRepositoryBadgesMarkup, resolveRepositoryLinkData } from '@features/models/modals/downloadmodal/mappers.ts';
import { getPluginDisplayName, locatePluginByName, resolvePluginUnavailableReason } from '@features/models/modals/downloadmodal/pluginAvailability.ts';
import { renderPluginOptions } from '@features/models/modals/downloadmodal/pluginOptionsRenderer.ts';

const applyDownloadPluginSelection = (host: DownloadModalHost, modalId: string, modalRoot: Element, pluginName: string, onSelectionApplied: () => void): string => {
    const resolver = createModalElementResolver(host.session.modals.requireElement(modalId), 'Download modal');
    const select = requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot);
    const normalizedName = toTrimmedString(pluginName);
    if (!normalizedName) {
        return select.value ?? '';
    }
    const plugin = locatePluginByName(host, normalizedName);
    if (!plugin || !host.catalog.isDownloadPluginOperational(plugin)) {
        return select.value ?? '';
    }
    const value = toTrimmedString(plugin.name) || normalizedName;
    host.view.setUIValue(select, value, { attribute: 'value' });
    onSelectionApplied();
    return value;
};

const applyProviderPluginSelection = (host: DownloadModalHost, modalId: string, modalRoot: Element, pluginName: string): string => {
    const resolver = createModalElementResolver(host.session.modals.requireElement(modalId), 'Download modal');
    const select = requireSelectElement(resolver, modalUiSelector(modalId, 'provider-plugin-select'), 'Download modal provider-plugin-select', modalRoot);
    const normalizedName = toTrimmedString(pluginName);
    if (!normalizedName) {
        return select.value ?? '';
    }
    const plugin = locatePluginByName(host, normalizedName);
    if (!plugin || !host.catalog.isProviderPluginOperational(plugin)) {
        return select.value ?? '';
    }
    const value = toTrimmedString(plugin.name) || normalizedName;
    host.view.setUIValue(select, value, { attribute: 'value' });
    return value;
};

const populateDownloadPluginDropdown = (host: DownloadModalHost, modalId: string, modalRoot: Element): void => {
    const resolver = createModalElementResolver(host.session.modals.requireElement(modalId), 'Download modal');
    const select = requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot);
    let plugins = host.catalog.getDownloadPlugins();
    if (!plugins.length) {
        try {
            host.catalog.refreshPluginCaches();
            plugins = host.catalog.getDownloadPlugins();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('DownloadModalController', 'Catalog store synchronization failed', runtimeError);
        }
    }
    renderPluginOptions({ host }, select, plugins, i18n.t('models.modal.addModel.pluginPlaceholder'), (plugin) => host.catalog.isDownloadPluginOperational(plugin), 'download');
    autoSelectSingleOperationalPlugin(host, select, plugins, (plugin) => host.catalog.isDownloadPluginOperational(plugin));
};

const populateProviderPluginDropdown = (host: DownloadModalHost, modalId: string, modalRoot: Element): void => {
    const resolver = createModalElementResolver(host.session.modals.requireElement(modalId), 'Download modal');
    const select = requireSelectElement(resolver, modalUiSelector(modalId, 'provider-plugin-select'), 'Download modal provider-plugin-select', modalRoot);
    let plugins = host.catalog.getProviderPlugins();
    if (!plugins.length) {
        try {
            host.catalog.refreshPluginCaches();
            plugins = host.catalog.getProviderPlugins();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('DownloadModalController', 'Catalog store synchronization failed', runtimeError);
        }
    }
    renderPluginOptions({ host }, select, plugins, i18n.t('models.modal.addProvider.pluginPlaceholder'), (plugin) => host.catalog.isProviderPluginOperational(plugin), 'provider');
    autoSelectSingleOperationalPlugin(host, select, plugins, (plugin) => host.catalog.isProviderPluginOperational(plugin));
};

const autoSelectSingleOperationalPlugin = (host: DownloadModalHost, select: HTMLSelectElement, plugins: PluginRecord[], isOperational: (plugin: PluginRecord) => boolean): void => {
    let availablePluginName = '';
    let availableCount = 0;
    for (const plugin of plugins) {
        const pluginName = toTrimmedString(plugin?.name);
        if (!pluginName || !isOperational(plugin)) {
            continue;
        }
        availablePluginName = pluginName;
        availableCount += 1;
        if (availableCount > 1) {
            return;
        }
    }
    if (availableCount === 1) {
        host.view.setUIValue(select, availablePluginName, { attribute: 'value' });
    }
};

const renderDownloadPluginWarning = (host: DownloadModalHost, modalId: string, modalRoot: Element, pluginName: string): void => {
    const container = host.session.requireHTMLElement(modalUiSelector(modalId, 'download-plugin-warning'), modalRoot);
    const hideWarning = (): void => {
        host.view.addClassName(container, CSS_CLASSES.HIDDEN);
        host.view.updateHTML(container, '');
    };
    if (!pluginName) {
        hideWarning();
        return;
    }
    const plugin = locatePluginByName(host, pluginName);
    if (!plugin) {
        hideWarning();
        return;
    }
    if (!host.catalog.isDownloadPluginOperational(plugin)) {
        const reason = resolvePluginUnavailableReason(plugin, 'download');
        host.view.updateHTML(container, uiHtml`<div class="form-disclaimer-text form-disclaimer-error">${reason}</div>`);
        host.view.removeClassName(container, CSS_CLASSES.HIDDEN);
        return;
    }
    const messages = getPluginSystemRequirementMessages(plugin, 'download_model');
    if (!messages.length) {
        hideWarning();
        return;
    }
    const disclaimerMarkup = toTrustedUiHtml(messages.map((message) => `<div class="form-disclaimer-text">${host.session.sanitizer.html(message)}</div>`).join(''));
    host.view.updateHTML(container, disclaimerMarkup);
    host.view.removeClassName(container, CSS_CLASSES.HIDDEN);
};

const updateRepositoryLink = (host: DownloadModalHost, modalId: string, modalRoot: Element): void => {
    const resolver = createModalElementResolver(host.session.modals.requireElement(modalId), 'Download modal');
    const pluginName = toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value);
    const modelId = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'model-id'), 'Download modal model-id', modalRoot).value);
    const group = host.session.requireHTMLElement(modalUiSelector(modalId, 'repository-link-group'), modalRoot);
    const link = host.session.requireHTMLElement(modalUiSelector(modalId, 'repository-link'), modalRoot);
    if (!(link instanceof HTMLAnchorElement)) {
        throw new Error(`Download modal repository-link must be an HTMLAnchorElement`);
    }
    const text = host.session.requireHTMLElement(modalUiSelector(modalId, 'repository-link-text'), modalRoot);
    const badgeContainer = host.session.requireHTMLElement(modalUiSelector(modalId, 'repository-badges-container'), modalRoot);

    const resetRepositoryLink = (): void => {
        host.view.addClassName(group, CSS_CLASSES.HIDDEN);
        host.view.setUIValue(link, '#', { attribute: 'href' });
        host.view.updateText(text, i18n.t('models.modal.addModel.repositoryLink'));
        host.view.updateHTML(badgeContainer, '');
    };

    if (!pluginName) {
        resetRepositoryLink();
        return;
    }
    const plugin = locatePluginByName(host, pluginName);
    if (!plugin) {
        resetRepositoryLink();
        return;
    }
    const repositoryData = resolveRepositoryLinkData(plugin, modelId);
    if (!repositoryData?.url) {
        resetRepositoryLink();
        return;
    }

    host.view.removeClassName(group, CSS_CLASSES.HIDDEN);
    const pluginDisplayName = getPluginDisplayName(plugin);
    host.view.setUIValue(link, repositoryData.url, { attribute: 'href' });
    if (pluginDisplayName) {
        host.view.updateText(text, i18n.t('models.modal.addModel.repositoryLinkWithProvider', { provider: pluginDisplayName }));
    } else {
        host.view.updateText(text, i18n.t('models.modal.addModel.repositoryLink'));
    }
    host.view.updateHTML(badgeContainer, buildRepositoryBadgesMarkup(host, plugin, repositoryData.badges));
};

export { applyDownloadPluginSelection, applyProviderPluginSelection, populateDownloadPluginDropdown, populateProviderPluginDropdown, renderDownloadPluginWarning, updateRepositoryLink };
