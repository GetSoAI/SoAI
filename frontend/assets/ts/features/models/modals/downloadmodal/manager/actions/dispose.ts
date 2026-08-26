/* SoAI - Models feature dispose [frontend/assets/ts/features/models/modals/downloadmodal/manager/actions/dispose.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { updateRepositoryLink } from '@features/models/modals/downloadmodal/effects.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { hasActiveModelDownloads } from '@features/models/modals/downloadmodal/manager/modelDownloadOperations.ts';
import { getManualDiscoveryState, getModelSearchState, resetManualDiscoveryState } from '@features/models/modals/downloadmodal/manager/state.ts';
import { cancelModelSearchRequest, updateDownloadModalUI, updatePluginRequiredMarkers, updateSelectedModelDisplay } from '@features/models/modals/downloadmodal/manager/view.ts';

const disposeDownloadModal = (runtime: DownloadModalManagerRuntime, { clearActiveDownloads = false }: { clearActiveDownloads?: boolean } = {}): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    updateDownloadModalUI(runtime, 'download');
    for (const id of ['provider-plugin-select', 'provider-name', 'provider-api-url', 'provider-api-key', 'provider-models-filter']) {
        const element = runtime.host.view.optionalHTMLElement(modalUiSelector(modalId, id), modalRoot);
        if (element) {
            runtime.host.view.setUIValue(element, '', { attribute: 'value' });
        }
    }
    for (const token of ['provider-details-group', 'provider-api-url-group', 'provider-api-key-group', 'provider-models-group']) {
        const group = runtime.host.view.optionalHTMLElement(modalUiSelector(modalId, token), modalRoot);
        if (group) {
            runtime.host.view.addClassName(group, CSS_CLASSES.HIDDEN);
        }
    }
    const hasActiveDownloads = hasActiveModelDownloads(runtime);
    for (const id of ['model-id', 'model-quant']) {
        const element = runtime.host.view.optionalHTMLElement(modalUiSelector(modalId, id), modalRoot);
        if (!element) {
            continue;
        }
        runtime.host.view.setUIValue(element, '', { attribute: 'value' });
    }
    if (!hasActiveDownloads || clearActiveDownloads) {
        for (const id of ['download-plugin-select']) {
            const element = runtime.host.view.optionalHTMLElement(modalUiSelector(modalId, id), modalRoot);
            if (!element) {
                continue;
            }
            runtime.host.view.setUIValue(element, '', { attribute: 'value' });
        }
        const operationProgressList = runtime.host.view.optionalHTMLElement(modalUiSelector(modalId, 'operation-progress-list'), modalRoot);
        if (operationProgressList) {
            runtime.host.view.updateHTML(operationProgressList, '');
        }
    }
    updateSelectedModelDisplay(runtime);
    runtime.host.execution.variantProbe.reset();
    runtime.host.execution.variantProbe.updateButtonState();
    cancelModelSearchRequest(runtime);
    const modelSearchState = getModelSearchState(runtime);
    modelSearchState.results = [];
    modelSearchState.selectedIndex = null;
    modelSearchState.plugin = '';
    const modelSearchInput = runtime.host.view.optionalHTMLElement(modalUiSelector(modalId, 'model-search-input'), modalRoot);
    if (modelSearchInput instanceof HTMLInputElement) {
        runtime.host.view.setUIValue(modelSearchInput, '', { attribute: 'value' });
    }
    const modelSearchResults = runtime.host.view.optionalHTMLElement(modalUiSelector(modalId, 'model-search-results'), modalRoot);
    if (modelSearchResults) {
        runtime.host.view.updateHTML(modelSearchResults, '');
        runtime.host.view.addClassName(modelSearchResults, CSS_CLASSES.HIDDEN);
    }
    const modelSearchGroup = runtime.host.view.optionalHTMLElement(modalUiSelector(modalId, 'model-search-group'), modalRoot);
    if (modelSearchGroup) {
        runtime.host.view.addClassName(modelSearchGroup, CSS_CLASSES.HIDDEN);
    }
    const manualDiscoveryState = getManualDiscoveryState(runtime);
    resetManualDiscoveryState(manualDiscoveryState);
    const repositoryLink = runtime.host.view.optionalHTMLElement(modalUiSelector(modalId, 'repository-link'), modalRoot);
    if (repositoryLink instanceof HTMLAnchorElement) {
        updateRepositoryLink(runtime.host, modalId, modalRoot);
    }
    updatePluginRequiredMarkers(runtime);
};

export { disposeDownloadModal };
