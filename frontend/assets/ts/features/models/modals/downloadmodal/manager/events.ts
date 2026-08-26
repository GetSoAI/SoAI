/* SoAI - Models feature manager events [frontend/assets/ts/features/models/modals/downloadmodal/manager/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { APIError } from '@core/apiError.ts';
import { optionalNonNegativeIntegerDataAttribute } from '@core/dom/attributes.ts';
import { requireInputElement, requireSelectElement } from '@core/dom/typedElements.ts';
import { getWindowOpen } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { securityApi } from '@core/security/public.ts';
import { isJsonValue } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { SanitizerApi } from '@core/pagecontext/contracts.ts';
import { MODEL_SEARCH_LIMIT, MODEL_SEARCH_MIN_QUERY } from '@features/models/modals/downloadmodal/downloadModalConfig.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { scrollDownloadModalSectionIntoView } from '@features/models/modals/downloadmodal/manager/scrolling.ts';
import { updateManualDiscoveryMessage } from '@features/models/modals/downloadmodal/manager/service.ts';
import { getModelSearchInputValue, getModelSearchState } from '@features/models/modals/downloadmodal/manager/state.ts';
import { handleVariantCheck } from '@features/models/modals/downloadmodal/manager/variantEvents.ts';
import { cancelModelSearchRequest, clearModelSearchResults, handleVariantInputChange, updateDownloadModalUI, updateModelSearchButtonState } from '@features/models/modals/downloadmodal/manager/view.ts';
import { parseModelSearchResults } from '@features/models/modals/downloadmodal/mappers.ts';
import { highlightModelSearchSelection, renderModelSearchError, renderModelSearchLoading, renderModelSearchResults } from '@features/models/modals/downloadmodal/modelSearchRendering.ts';

type Sanitizer = Pick<SanitizerApi, 'attribute' | 'html'>;

const handleModelSearchInput = (runtime: DownloadModalManagerRuntime, _event?: Event): void => {
    const state = getModelSearchState(runtime);
    state.selectedIndex = null;
    if (!getModelSearchInputValue(runtime)) {
        state.results = [];
        clearModelSearchResults(runtime, true);
    }
    updateModelSearchButtonState(runtime);
};

const handleModelSearchInputKeydown = (runtime: DownloadModalManagerRuntime, event: Event): void => {
    if (!(event instanceof KeyboardEvent)) {
        return;
    }
    if (event.key !== 'Enter') {
        return;
    }
    event.preventDefault();
    terminateHandledPromise(handleModelSearch(runtime));
};

const isModelSearchTokenActive = (runtime: DownloadModalManagerRuntime, token: symbol): boolean => {
    return getModelSearchState(runtime).token === token;
};

const isModelSearchAbort = <T>(error: T): boolean => {
    if (isAbortError(error)) {
        return true;
    }
    if (!(error instanceof APIError) || error.status !== 0) {
        return false;
    }
    const cause = error.cause;
    return isAbortError(cause) || isAbortError(error.message);
};

const handleModelSearch = async (runtime: DownloadModalManagerRuntime, event?: Event): Promise<void> => {
    if (event) {
        event.preventDefault();
    }

    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const plugin = toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value);
    const query = getModelSearchInputValue(runtime);
    if (!plugin || query.length < MODEL_SEARCH_MIN_QUERY) {
        updateModelSearchButtonState(runtime);
        return;
    }

    const state = getModelSearchState(runtime);
    cancelModelSearchRequest(runtime);

    const abortController = new AbortController();
    const token = Symbol('modelSearch');
    state.loading = true;
    state.token = token;
    state.abortController = abortController;
    state.selectedIndex = null;

    const sanitizer: Sanitizer = runtime.host.session.sanitizer;
    renderModelSearchLoading({ host: runtime.host, sanitizer, modalId, modalRoot });
    updateModelSearchButtonState(runtime);

    try {
        const results = await runtime.host.execution.modelActions.searchRemoteModels(plugin, query, {
            limit: MODEL_SEARCH_LIMIT,
            signal: abortController.signal
        });

        if (!isModelSearchTokenActive(runtime, token)) {
            return;
        }

        state.results = parseModelSearchResults(isJsonValue(results) ? results : undefined);
        renderModelSearchResults({
            host: runtime.host,
            sanitizer,
            results: state.results,
            selectedIndex: state.selectedIndex,
            modalId,
            modalRoot
        });
        state.loading = false;
        state.abortController = null;
        state.token = null;
        updateModelSearchButtonState(runtime);
    } catch (error) {
        if (!isModelSearchTokenActive(runtime, token)) {
            return;
        }
        if (isModelSearchAbort(error)) {
            state.loading = false;
            state.abortController = null;
            state.token = null;
            updateModelSearchButtonState(runtime);
            return;
        }
        const runtimeError = ensureError(error);
        errorHandler.error('DownloadModalController', 'Failed to search remote models', runtimeError);
        renderModelSearchError({ host: runtime.host, sanitizer, message: null, modalId, modalRoot });
        state.loading = false;
        state.abortController = null;
        state.token = null;
        updateModelSearchButtonState(runtime);
    }
};

const handleModelSearchResultClick = (runtime: DownloadModalManagerRuntime, event: Event, target: Element): void => {
    event.preventDefault();
    applyModelSearchSelection(runtime, target);
};

const handleModelSearchResultKeydown = (runtime: DownloadModalManagerRuntime, event: Event, target: Element): void => {
    if (!(event instanceof KeyboardEvent)) {
        return;
    }
    if (event.key !== 'Enter' && event.key !== ' ') {
        return;
    }
    event.preventDefault();
    applyModelSearchSelection(runtime, target);
};

const applyModelSearchSelection = (runtime: DownloadModalManagerRuntime, target: Element): void => {
    if (!target) {
        return;
    }

    const index = optionalNonNegativeIntegerDataAttribute(target, 'result-index', 'Model search result');
    if (index === null) {
        return;
    }

    const state = getModelSearchState(runtime);
    const entry = state.results[index];
    if (!isObject(entry)) {
        return;
    }

    const modelId = toTrimmedString(entry['id']) || toTrimmedString(entry['name']);
    if (!modelId) {
        return;
    }

    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const input = requireInputElement(resolver, modalUiSelector(modalId, 'model-id'), 'Download modal model-id', modalRoot);
    runtime.host.view.setUIValue(input, modelId, { attribute: 'value' });
    state.selectedIndex = index;
    highlightModelSearchSelection({ host: runtime.host, selectedIndex: state.selectedIndex, modalId, modalRoot });

    handleVariantInputChange(runtime);
    terminateHandledPromise(handleVariantCheck(runtime));
    scrollDownloadModalSectionIntoView(runtime, 'model-id-group');
    input.focus();
};

const handleModelIdGroupScrollTriggerClick = (runtime: DownloadModalManagerRuntime, event: Event, _target: Element): void => {
    event.preventDefault();
    scrollDownloadModalSectionIntoView(runtime, 'model-id-group');
};

const handleRepositoryLinkClick = async (runtime: DownloadModalManagerRuntime, _event?: Event): Promise<void> => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const link = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'repository-link'), modalRoot);
    if (!(link instanceof HTMLAnchorElement)) {
        throw new Error('Download modal repository-link must be an HTMLAnchorElement');
    }
    const url = link.href;
    if (
        !url ||
        url === '#' ||
        !(await requireDialogsService().showExternalLinkModal({
            title: i18n.t('models.confirmations.externalLink'),
            message: i18n.t('models.confirmations.externalLinkMessage'),
            url,
            confirmText: i18n.t('models.confirmations.externalLinkConfirm'),
            cancelText: i18n.t('models.confirmations.externalLinkCancel'),
            variant: 'info',
            icon: 'external-link'
        }))
    ) {
        return;
    }

    const sanitizedUrl = securityApi.sanitizeUrl(url, {
        allowRelative: false,
        allowDataImage: false,
        allowBlob: false
    });
    if (!sanitizedUrl) {
        errorHandler.error('DownloadModalManager', 'Repository link URL failed sanitization', { url });
        runtime.host.session.showNotification(i18n.t('ui.errors.invalidUrl'), 'error');
        return;
    }

    getWindowOpen()(sanitizedUrl, '_blank', 'noopener,noreferrer');
};

const handleManualTabClick = async (runtime: DownloadModalManagerRuntime, _event?: Event): Promise<void> => {
    if (!runtime.host.session.isAdmin()) {
        updateDownloadModalUI(runtime, 'download');
        return;
    }
    updateDownloadModalUI(runtime, 'manual');
    await updateManualDiscoveryMessage(runtime);
};

export { applyModelSearchSelection, handleManualTabClick, handleModelIdGroupScrollTriggerClick, handleModelSearch, handleModelSearchInput, handleModelSearchInputKeydown, handleModelSearchResultClick, handleModelSearchResultKeydown, handleRepositoryLinkClick, handleVariantCheck, isModelSearchTokenActive };
