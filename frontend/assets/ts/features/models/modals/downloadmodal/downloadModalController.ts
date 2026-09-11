/* SoAI - Models download modal controller (event binding + orchestration) [frontend/assets/ts/features/models/modals/downloadmodal/downloadModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { createTaskOperationPanel, type TaskOperationPanel } from '@core/tasks/operationpanel/service.ts';
import { createInitialDownloadModalState, type DownloadModalState } from '@features/models/modals/downloadmodal/downloadModalState.ts';
import type { DownloadModalHost } from '@features/models/modals/downloadmodal/downloadModalTypes.ts';
import { handleConfirmAction } from '@features/models/modals/downloadmodal/manager/actions/confirmAction.ts';
import { disposeDownloadModal } from '@features/models/modals/downloadmodal/manager/actions/dispose.ts';
import { hasActiveModelDownloads } from '@features/models/modals/downloadmodal/manager/modelDownloadOperations.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { handleManualTabClick, handleModelSearch, handleModelSearchInput, handleModelSearchInputKeydown, handleModelSearchResultClick, handleModelSearchResultKeydown, handleRepositoryLinkClick } from '@features/models/modals/downloadmodal/manager/events.ts';
import { handleManualDiscovery, handleManualOpenFileExplorer, handleManualPathCopy } from '@features/models/modals/downloadmodal/manager/service.ts';
import { handleVariantCheck } from '@features/models/modals/downloadmodal/manager/variantEvents.ts';
import { handleDownloadTabClick, handlePluginSelectChange, handleProviderPluginSelectChange, handleProviderTabClick, handleVariantInputChange, openDownloadModelModal, updateDownloadBadge, updateDownloadButtonState, updateSelectedModelDisplay } from '@features/models/modals/downloadmodal/manager/view.ts';
import { MODELS_DOWNLOAD_MODAL_ID } from '@features/models/modals/constants.ts';
import { MODEL_DOWNLOAD_OPERATION_FILTER } from '@features/models/modelDownloadOperation.ts';

type DownloadModalController = {
    modalId: string;
    bindModalEventListeners: (signal: AbortSignal) => void;
    open: (event?: Event) => void;
    openProviderTab: (event?: Event) => void;
    updateBadge: () => void;
    onModalClosed: () => void;
    disposeForPageDestroy: () => void;
    hasActiveModelDownloads: () => boolean;
};

const createDownloadModalController = (dependencies: { host: DownloadModalHost }): DownloadModalController => {
    const modalId = MODELS_DOWNLOAD_MODAL_ID;
    const host = dependencies.host;
    const state: DownloadModalState = createInitialDownloadModalState();
    let operationPanel: TaskOperationPanel | null = null;

    const runtime = (): DownloadModalManagerRuntime => {
        return {
            host,
            state,
            modalId
        };
    };

    const attachOperationPanel = (): void => {
        operationPanel?.detach();
        operationPanel = createTaskOperationPanel({
            container: modalUiId(modalId, 'operation-progress-list'),
            filter: MODEL_DOWNLOAD_OPERATION_FILTER
        });
        operationPanel.attach();
    };

    const detachOperationPanel = (): void => {
        operationPanel?.detach();
        operationPanel = null;
    };

    const resolveEventElement = (event: Event): Element | null => {
        const target = event.target;
        return target instanceof Element ? target : null;
    };

    const bindModalEventListeners = (signal: AbortSignal): void => {
        const modalRoot = host.session.modals.requireElement(modalId);

        modalRoot.addEventListener(
            'click',
            (event: Event): void => {
                const element = resolveEventElement(event);
                if (!element) {
                    return;
                }

                const searchItem = element.closest('.search-item');
                if (searchItem instanceof Element) {
                    handleModelSearchResultClick(runtime(), event, searchItem);
                    return;
                }

                const variantEntry = element.closest('.variant-check-entry');
                if (variantEntry instanceof Element) {
                    if (host.execution.variantProbe.handleEntryClick(event, variantEntry)) {
                        updateSelectedModelDisplay(runtime());
                        updateDownloadButtonState(runtime());
                    }
                    return;
                }

                const actionButton = element.closest('button, a');
                if (!(actionButton instanceof HTMLElement)) {
                    return;
                }

                switch (actionButton.id) {
                    case modalUiId(modalId, 'confirm-download'):
                        handleConfirmAction(runtime(), event);
                        return;
                    case modalUiId(modalId, 'download-tab'):
                        handleDownloadTabClick(runtime(), event);
                        return;
                    case modalUiId(modalId, 'provider-tab'):
                        handleProviderTabClick(runtime(), event);
                        return;
                    case modalUiId(modalId, 'manual-tab'):
                        terminateHandledPromise(handleManualTabClick(runtime(), event));
                        return;
                    case modalUiId(modalId, 'model-search-button'):
                        terminateHandledPromise(handleModelSearch(runtime(), event));
                        return;
                    case modalUiId(modalId, 'model-variant-check'):
                        terminateHandledPromise(handleVariantCheck(runtime(), event));
                        return;
                    case modalUiId(modalId, 'variant-search-button'):
                        host.execution.variantProbe.applyVariantFilter();
                        return;
                    case modalUiId(modalId, 'manual-discovery-button'):
                        terminateHandledPromise(handleManualDiscovery(runtime(), event));
                        return;
                    case modalUiId(modalId, 'manual-copy-path'):
                        terminateHandledPromise(handleManualPathCopy(runtime(), event));
                        return;
                    case modalUiId(modalId, 'manual-open-file-explorer'):
                        handleManualOpenFileExplorer(runtime(), event);
                        return;
                    case modalUiId(modalId, 'repository-link'):
                        terminateHandledPromise(handleRepositoryLinkClick(runtime(), event));
                        return;
                    default:
                        return;
                }
            },
            { signal }
        );

        modalRoot.addEventListener(
            'input',
            (event: Event): void => {
                const target = resolveEventElement(event);
                if (!(target instanceof HTMLElement)) {
                    return;
                }
                switch (target.id) {
                    case modalUiId(modalId, 'model-search-input'):
                        handleModelSearchInput(runtime(), event);
                        return;
                    case modalUiId(modalId, 'variant-search-input'):
                        host.execution.variantProbe.applyVariantFilter();
                        return;
                    case modalUiId(modalId, 'model-id'):
                    case modalUiId(modalId, 'model-quant'):
                        handleVariantInputChange(runtime());
                        return;
                    case modalUiId(modalId, 'provider-name'):
                    case modalUiId(modalId, 'provider-api-url'):
                    case modalUiId(modalId, 'provider-api-key'):
                    case modalUiId(modalId, 'provider-models-filter'):
                        updateDownloadButtonState(runtime());
                        return;
                    default:
                        return;
                }
            },
            { signal }
        );

        modalRoot.addEventListener(
            'change',
            (event: Event): void => {
                const target = resolveEventElement(event);
                if (!(target instanceof HTMLElement)) {
                    return;
                }
                switch (target.id) {
                    case modalUiId(modalId, 'download-plugin-select'):
                        handlePluginSelectChange(runtime(), event);
                        return;
                    case modalUiId(modalId, 'provider-plugin-select'):
                        handleProviderPluginSelectChange(runtime(), event);
                        return;
                    case modalUiId(modalId, 'model-id'):
                    case modalUiId(modalId, 'model-quant'):
                        handleVariantInputChange(runtime());
                        return;
                    case modalUiId(modalId, 'provider-name'):
                    case modalUiId(modalId, 'provider-api-url'):
                    case modalUiId(modalId, 'provider-api-key'):
                    case modalUiId(modalId, 'provider-models-filter'):
                        updateDownloadButtonState(runtime());
                        return;
                    default:
                        return;
                }
            },
            { signal }
        );

        modalRoot.addEventListener(
            'keydown',
            (event: Event): void => {
                const element = resolveEventElement(event);
                if (!element) {
                    return;
                }
                if (typeof KeyboardEvent !== 'function' || !(event instanceof KeyboardEvent)) {
                    return;
                }

                const searchItem = element.closest('.search-item');
                if (searchItem instanceof Element) {
                    handleModelSearchResultKeydown(runtime(), event, searchItem);
                    return;
                }

                const variantEntry = element.closest('.variant-check-entry');
                if (variantEntry instanceof Element) {
                    if (host.execution.variantProbe.handleEntryKeydown(event, variantEntry)) {
                        updateSelectedModelDisplay(runtime());
                        updateDownloadButtonState(runtime());
                    }
                    return;
                }

                if (element instanceof HTMLElement && element.id === modalUiId(modalId, 'model-search-input')) {
                    handleModelSearchInputKeydown(runtime(), event);
                    return;
                }
                if (element instanceof HTMLElement && element.id === modalUiId(modalId, 'variant-search-input') && event.key === 'Enter') {
                    event.preventDefault();
                    host.execution.variantProbe.applyVariantFilter();
                    return;
                }
            },
            { signal }
        );
    };

    return {
        modalId,
        bindModalEventListeners,
        open: (event?: Event) => {
            attachOperationPanel();
            openDownloadModelModal(runtime(), event);
        },
        openProviderTab: (event?: Event) => {
            attachOperationPanel();
            openDownloadModelModal(runtime(), event);
            handleProviderTabClick(runtime());
        },
        updateBadge: () => updateDownloadBadge(runtime()),
        onModalClosed: () => {
            const shouldRefreshModels = state.acceptedCatalogMutation;
            state.acceptedCatalogMutation = false;
            detachOperationPanel();
            disposeDownloadModal(runtime());
            if (shouldRefreshModels) {
                host.execution.refreshModelsAfterCatalogMutation();
            }
        },
        disposeForPageDestroy: () => {
            state.acceptedCatalogMutation = false;
            detachOperationPanel();
            disposeDownloadModal(runtime(), { clearActiveDownloads: true });
        },
        hasActiveModelDownloads: () => hasActiveModelDownloads(runtime())
    };
};

export { createDownloadModalController };
export type { DownloadModalController };
