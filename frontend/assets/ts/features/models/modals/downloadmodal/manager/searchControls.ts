/* SoAI - Models feature search controls [frontend/assets/ts/features/models/modals/downloadmodal/manager/searchControls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { requireInputElement, requireSelectElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { MODEL_SEARCH_MIN_QUERY } from '@features/models/modals/downloadmodal/downloadModalConfig.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { getModelSearchInputValue, getModelSearchState } from '@features/models/modals/downloadmodal/manager/state.ts';

const handleModelSearchPluginChange = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const nextPlugin = toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value);
    const state = getModelSearchState(runtime);
    const hasPlugin = Boolean(nextPlugin);
    if (!hasPlugin) {
        resetModelSearchState(runtime, { clearInput: true });
    } else if (nextPlugin !== (state.plugin ?? '')) {
        resetModelSearchState(runtime, { hideContainer: true, clearInput: false });
    }
    state.plugin = nextPlugin;
    updateModelSearchVisibility(runtime, hasPlugin);
    updateModelSearchButtonState(runtime);
    updateModelSearchPlaceholder(runtime, nextPlugin);
};

const updateModelSearchPlaceholder = (runtime: DownloadModalManagerRuntime, pluginName: string): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const input = requireInputElement(resolver, modalUiSelector(modalId, 'model-search-input'), 'Download modal model-search-input', modalRoot);
    const placeholder = pluginName ? i18n.t('models.modal.addModel.searchPlaceholder', { plugin: pluginName }) : '';
    runtime.host.view.updateAttribute(input, 'placeholder', placeholder);
};

const updateModelIdGroupVisibility = (runtime: DownloadModalManagerRuntime, hasPlugin: boolean): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const group = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'model-id-group'), modalRoot);
    runtime.host.view.toggleClassName(group, CSS_CLASSES.HIDDEN, !hasPlugin);
};

const updateModelSearchVisibility = (runtime: DownloadModalManagerRuntime, shouldShow: boolean): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const group = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'model-search-group'), modalRoot);
    runtime.host.view.toggleClassName(group, CSS_CLASSES.HIDDEN, !shouldShow);
    if (!shouldShow) {
        clearModelSearchResults(runtime, true);
    }
};

const clearModelSearchResults = (runtime: DownloadModalManagerRuntime, hide = false): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const container = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'model-search-results'), modalRoot);
    runtime.host.view.updateHTML(container, '');
    if (hide) {
        runtime.host.view.addClassName(container, CSS_CLASSES.HIDDEN);
    }
};

const resetModelSearchState = (runtime: DownloadModalManagerRuntime, options: { cancel?: boolean; clearInput?: boolean; hideContainer?: boolean } = {}): void => {
    const state = getModelSearchState(runtime);
    state.results = [];
    state.selectedIndex = null;
    state.plugin = '';
    if (options.cancel !== false) {
        cancelModelSearchRequest(runtime);
    }
    if (options.clearInput) {
        const modalId = runtime.modalId;
        const modalRoot = runtime.host.session.modals.requireElement(modalId);
        const resolver = createModalElementResolver(modalRoot, 'Download modal');
        runtime.host.view.setUIValue(requireInputElement(resolver, modalUiSelector(modalId, 'model-search-input'), 'Download modal model-search-input', modalRoot), '', {
            attribute: 'value'
        });
    }
    clearModelSearchResults(runtime, options.hideContainer !== false);
    updateModelSearchButtonState(runtime);
};

const updateModelSearchButtonState = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const button = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'model-search-button'), modalRoot);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const hasPlugin = Boolean(toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value));
    const canSearch = hasPlugin && getModelSearchInputValue(runtime).length >= MODEL_SEARCH_MIN_QUERY && !getModelSearchState(runtime).loading;
    runtime.host.view.updateProperty(button, 'disabled', !canSearch);
};

const cancelModelSearchRequest = (runtime: DownloadModalManagerRuntime): void => {
    const state = getModelSearchState(runtime);
    if (state.abortController) {
        try {
            state.abortController.abort();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('DownloadModalController', 'Aborting model search failed', runtimeError);
        }
    }
    state.abortController = null;
    state.token = null;
    state.loading = false;
};

export { cancelModelSearchRequest, clearModelSearchResults, handleModelSearchPluginChange, resetModelSearchState, updateModelIdGroupVisibility, updateModelSearchButtonState, updateModelSearchPlaceholder, updateModelSearchVisibility };
