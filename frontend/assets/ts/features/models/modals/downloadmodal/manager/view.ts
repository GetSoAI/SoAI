/* SoAI - Models feature manager rendering [frontend/assets/ts/features/models/modals/downloadmodal/manager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { requireInputElement, requireSelectElement } from '@core/dom/typedElements.ts';
import { splitModelVariantInput } from '@core/modelactions/variantInput.ts';
import { MODELS_ACTION_ADD_PROVIDER } from '@core/models/pageActions.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { resolveNotifyBadgeText } from '@core/ui/controls/tabs/service.ts';
import { applyDownloadPluginSelection, applyProviderPluginSelection, populateDownloadPluginDropdown, populateProviderPluginDropdown, renderDownloadPluginWarning, updateRepositoryLink } from '@features/models/modals/downloadmodal/effects.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { countActiveModelDownloads } from '@features/models/modals/downloadmodal/manager/modelDownloadOperations.ts';
import { cancelModelSearchRequest, clearModelSearchResults, handleModelSearchPluginChange, resetModelSearchState, updateModelIdGroupVisibility, updateModelSearchButtonState, updateModelSearchPlaceholder, updateModelSearchVisibility } from '@features/models/modals/downloadmodal/manager/searchControls.ts';
import { updateDownloadModalUI, updateModalTabsVisibility, updateVariantControlsVisibility } from '@features/models/modals/downloadmodal/manager/tabsView.ts';

const openDownloadModelModal = (runtime: DownloadModalManagerRuntime, _event?: Event): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const rawContext = runtime.host.session.consumeInitialActionContext();
    const context = isObject(rawContext) ? rawContext : null;
    const shouldOpenProviderTab = context?.['action'] === MODELS_ACTION_ADD_PROVIDER;
    populatePluginDropdowns(runtime);
    updateDownloadBadge(runtime);
    resetModelSearchState(runtime, { clearInput: true, hideContainer: true });
    updateModelSearchVisibility(runtime, false);
    if (context?.['plugin']) {
        const plugin = isString(context['plugin']) ? context['plugin'] : '';
        const selected = applyDownloadPluginSelection(runtime.host, modalId, modalRoot, plugin, () => handlePluginSelectChange(runtime));
        if (!selected) {
            handlePluginSelectChange(runtime);
        }
        if (shouldOpenProviderTab) {
            applyProviderPluginSelection(runtime.host, modalId, modalRoot, plugin);
            applyProviderDefaults(runtime);
        }
    }
    updateRepositoryLink(runtime.host, modalId, modalRoot);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const pluginValue = toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value);
    renderDownloadPluginWarning(runtime.host, modalId, modalRoot, pluginValue);
    handleModelSearchPluginChange(runtime);
    updateModelIdGroupVisibility(runtime, Boolean(toTrimmedString(pluginValue)));
    updateModalTabsVisibility(runtime, !shouldOpenProviderTab);
    updateDownloadModalUI(runtime, shouldOpenProviderTab ? 'provider' : 'download');
    updateProviderFieldsVisibility(runtime);
    updatePluginRequiredMarkers(runtime);
    runtime.host.execution.variantProbe.reset();
    runtime.host.execution.variantProbe.updateButtonState();
    updateSelectedModelDisplay(runtime);
    updateDownloadButtonState(runtime);
    runtime.host.session.modals.open(runtime.modalId);
};
const closeDownloadModelModal = (runtime: DownloadModalManagerRuntime, _event?: Event): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    updateDownloadModalUI(runtime, 'download');
    runtime.host.view.setUIValue(runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-plugin-select'), modalRoot), '', { attribute: 'value' });
    ['provider-name', 'provider-api-url', 'provider-api-key', 'provider-models-filter'].forEach((id) => {
        const input = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, id), modalRoot);
        runtime.host.view.setUIValue(input, '', { attribute: 'value' });
    });
    updateProviderFieldsVisibility(runtime);
    updatePluginRequiredMarkers(runtime);
    runtime.host.execution.variantProbe.reset();
    runtime.host.execution.variantProbe.updateButtonState();
    updateSelectedModelDisplay(runtime);
    runtime.host.session.modals.close(runtime.modalId);
};
const handlePluginSelectChange = (runtime: DownloadModalManagerRuntime, _event?: Event): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    clearDownloadFormFields(runtime);
    updateRepositoryLink(runtime.host, modalId, modalRoot);
    handleVariantInputChange(runtime);
    const downloadPluginValue = toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value);
    renderDownloadPluginWarning(runtime.host, modalId, modalRoot, downloadPluginValue);
    handleModelSearchPluginChange(runtime);
    const hasPlugin = Boolean(downloadPluginValue);
    updateModelIdGroupVisibility(runtime, hasPlugin);
    updatePluginRequiredMarkers(runtime);
    updateDownloadButtonState(runtime);
};
const clearDownloadFormFields = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    runtime.host.view.setUIValue(requireInputElement(resolver, modalUiSelector(modalId, 'model-id'), 'Download modal model-id', modalRoot), '', { attribute: 'value' });
    runtime.host.view.setUIValue(requireInputElement(resolver, modalUiSelector(modalId, 'model-quant'), 'Download modal model-quant', modalRoot), '', { attribute: 'value' });
    runtime.host.view.setUIValue(requireInputElement(resolver, modalUiSelector(modalId, 'model-search-input'), 'Download modal model-search-input', modalRoot), '', { attribute: 'value' });
};
const handleProviderPluginSelectChange = (runtime: DownloadModalManagerRuntime, _event?: Event): void => {
    clearProviderFormFields(runtime);
    applyProviderDefaults(runtime);
    updateProviderFieldsVisibility(runtime);
    updatePluginRequiredMarkers(runtime);
    updateDownloadButtonState(runtime);
};
const applyProviderDefaults = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const pluginName = toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'provider-plugin-select'), 'Download modal provider-plugin-select', modalRoot).value);
    const plugin = runtime.host.catalog.getPluginByName(pluginName);
    const defaults = isObject(plugin?.externalProviderDefaults) ? plugin.externalProviderDefaults : null;
    if (!defaults) {
        return;
    }
    const providerName = toTrimmedString(defaults['name']);
    const providerApiUrl = toTrimmedString(defaults['api_url']);
    if (providerName) {
        runtime.host.view.setUIValue(requireInputElement(resolver, modalUiSelector(modalId, 'provider-name'), 'Download modal provider-name', modalRoot), providerName, { attribute: 'value' });
    }
    if (providerApiUrl) {
        runtime.host.view.setUIValue(requireInputElement(resolver, modalUiSelector(modalId, 'provider-api-url'), 'Download modal provider-api-url', modalRoot), providerApiUrl, { attribute: 'value' });
    }
};
const clearProviderFormFields = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    runtime.host.view.setUIValue(requireInputElement(resolver, modalUiSelector(modalId, 'provider-name'), 'Download modal provider-name', modalRoot), '', { attribute: 'value' });
    runtime.host.view.setUIValue(requireInputElement(resolver, modalUiSelector(modalId, 'provider-api-url'), 'Download modal provider-api-url', modalRoot), '', { attribute: 'value' });
    runtime.host.view.setUIValue(requireInputElement(resolver, modalUiSelector(modalId, 'provider-api-key'), 'Download modal provider-api-key', modalRoot), '', { attribute: 'value' });
    runtime.host.view.setUIValue(requireInputElement(resolver, modalUiSelector(modalId, 'provider-models-filter'), 'Download modal provider-models-filter', modalRoot), '', { attribute: 'value' });
};
const handleVariantInputChange = (runtime: DownloadModalManagerRuntime, _event?: Event): void => {
    runtime.host.execution.variantProbe.reset();
    updateVariantControlsVisibility(runtime);
    updateSelectedModelDisplay(runtime);
    updateDownloadButtonState(runtime);
};
const updateSelectedModelDisplay = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const display = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'selected-model-display'), modalRoot);
    const downloadTab = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'download-tab'), modalRoot);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const isDownloadTabActive = runtime.host.session.dom.hasClass(downloadTab, CSS_CLASSES.ACTIVE);
    const hasPlugin = Boolean(toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value));
    const modelId = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'model-id'), 'Download modal model-id', modalRoot).value);

    const shouldShow = isDownloadTabActive && hasPlugin && Boolean(modelId);
    runtime.host.view.toggleClassName(display, CSS_CLASSES.HIDDEN, !shouldShow);
    runtime.host.view.updateAttribute(display, 'aria-hidden', shouldShow ? 'false' : 'true');
    if (!shouldShow) {
        return;
    }

    const inlineVariant = splitModelVariantInput(modelId);
    const quant = inlineVariant.variantToken || toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'model-quant'), 'Download modal model-quant', modalRoot).value);
    const displayModelId = inlineVariant.variantToken ? inlineVariant.modelId : modelId;
    runtime.host.view.updateText(runtime.host.session.requireHTMLElement('.download-model-selected-model-id', display), displayModelId);
    runtime.host.view.updateText(runtime.host.session.requireHTMLElement('.download-model-selected-model-quant', display), quant);
};
const updateProviderFieldsVisibility = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const hasPlugin = Boolean(toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'provider-plugin-select'), 'Download modal provider-plugin-select', modalRoot).value));
    const groups = ['provider-details-group', 'provider-api-url-group', 'provider-api-key-group', 'provider-models-group'];
    for (const token of groups) {
        const group = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, token), modalRoot);
        runtime.host.view.toggleClassName(group, CSS_CLASSES.HIDDEN, !hasPlugin);
    }
};
const updatePluginRequiredMarkers = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const downloadMarker = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'download-plugin-required-marker'), modalRoot);
    const providerMarker = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-plugin-required-marker'), modalRoot);
    const hasDownloadPlugin = Boolean(toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value));
    const hasProviderPlugin = Boolean(toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'provider-plugin-select'), 'Download modal provider-plugin-select', modalRoot).value));
    runtime.host.view.toggleClassName(downloadMarker, CSS_CLASSES.HIDDEN, !hasDownloadPlugin);
    runtime.host.view.toggleClassName(providerMarker, CSS_CLASSES.HIDDEN, !hasProviderPlugin);
};
const updateDownloadButtonState = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const confirmButton = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'confirm-download'), modalRoot);
    const downloadTab = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'download-tab'), modalRoot);
    const providerTab = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-tab'), modalRoot);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const isDownloadTabActive = runtime.host.session.dom.hasClass(downloadTab, CSS_CLASSES.ACTIVE);
    if (isDownloadTabActive) {
        const hasPlugin = Boolean(toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value));
        const hasModelId = Boolean(toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'model-id'), 'Download modal model-id', modalRoot).value));
        runtime.host.view.updateProperty(confirmButton, 'disabled', !(hasPlugin && hasModelId));
        return;
    }
    if (runtime.host.session.dom.hasClass(providerTab, CSS_CLASSES.ACTIVE)) {
        const hasPlugin = Boolean(toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'provider-plugin-select'), 'Download modal provider-plugin-select', modalRoot).value));
        const hasProviderName = Boolean(toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'provider-name'), 'Download modal provider-name', modalRoot).value));
        const hasProviderApiUrl = Boolean(toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'provider-api-url'), 'Download modal provider-api-url', modalRoot).value));
        const hasProviderApiKey = Boolean(toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'provider-api-key'), 'Download modal provider-api-key', modalRoot).value));
        const hasRequiredFields = hasPlugin && hasProviderName && hasProviderApiUrl && hasProviderApiKey;
        runtime.host.view.updateProperty(confirmButton, 'disabled', runtime.state.isCreatingProvider || !hasRequiredFields);
        return;
    }
    runtime.host.view.updateProperty(confirmButton, 'disabled', false);
};
const handleDownloadTabClick = (runtime: DownloadModalManagerRuntime, _event?: Event): void => {
    updateDownloadModalUI(runtime, 'download');
    updateDownloadButtonState(runtime);
};
const handleProviderTabClick = (runtime: DownloadModalManagerRuntime, _event?: Event): void => {
    updateDownloadModalUI(runtime, 'provider');
    updateProviderFieldsVisibility(runtime);
    updateDownloadButtonState(runtime);
};
const populatePluginDropdowns = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    populateDownloadPluginDropdown(runtime.host, modalId, modalRoot);
    populateProviderPluginDropdown(runtime.host, modalId, modalRoot);
};

const updateDownloadBadge = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const badge = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'download-notify'), modalRoot);
    const count = countActiveModelDownloads(runtime);
    runtime.host.view.updateText(badge, resolveNotifyBadgeText(count));
    runtime.host.view.toggleClassName(badge, CSS_CLASSES.HIDDEN, count === 0);
};

export { cancelModelSearchRequest, clearDownloadFormFields, clearModelSearchResults, clearProviderFormFields, closeDownloadModelModal, handleDownloadTabClick, handleModelSearchPluginChange, handlePluginSelectChange, handleProviderPluginSelectChange, handleProviderTabClick, handleVariantInputChange, openDownloadModelModal, populatePluginDropdowns, resetModelSearchState, updateDownloadBadge, updateDownloadButtonState, updateDownloadModalUI, updateModelIdGroupVisibility, updateModelSearchButtonState, updateModelSearchPlaceholder, updateModelSearchVisibility, updateModalTabsVisibility, updatePluginRequiredMarkers, updateSelectedModelDisplay };
