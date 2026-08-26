/* SoAI - Model detail page control layer event listeners [frontend/assets/ts/pages/modeldetail/controllers/page/eventListeners.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dom } from '@core/dom/dom.ts';
import { getWindow } from '@core/environment/public.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import { MODELS_ACTION_MANAGE_VIRTUAL_MODELS } from '@core/models/pageActions.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { MODELS_RENAME_MODEL_MODAL_ID, RenameModelModalManager } from '@features/models/public.ts';
import { createModelDetailActionHandlers } from '@pages/modeldetail/controllers/modelDetailActionHandlers.ts';
import { resetModelDetailOpenAICapabilityOverrides, toggleModelDetailOpenAICapabilityOverride } from '@pages/modeldetail/controllers/openaicapabilities/overrideActions.ts';
import { resetAllModelDetailParameters, type ModelDetailActionsHost } from '@pages/modeldetail/controllers/page/actionEffects.ts';
import { handleModelDetailLanguageChanged } from '@pages/modeldetail/controllers/page/dom.ts';
import { deleteModelDetailModel, stopModelDetailPlugin } from '@pages/modeldetail/controllers/page/operations/effects.ts';
import { handleModelDetailBackendDocumentationClick } from '@pages/modeldetail/controllers/page/view/service.ts';
import { persistModelDetailParameterFilter } from '@pages/modeldetail/controllers/parameterviewmanager/parameterViewControlsManager.ts';
import type { ModelDetailViewHost } from '@pages/modeldetail/controllers/page/view/types.ts';
import type { ModelDetailUi } from '@pages/modeldetail/dom.ts';
import { toggleModelDetailEnabled } from '@pages/modeldetail/state/enabled/enableActions.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';

type ModelDetailOperationsHost = Parameters<typeof deleteModelDetailModel>[0];

type RouterContract = {
    navigate: (pageId: string) => void;
    navigateWithQuery?: (pageId: string, query: Record<string, string>) => void;
};

type ParameterViewContract = {
    handleFilterSelection: (value: string) => void;
    addArrayItem: (parameterKey: string) => void;
    removeArrayItem: (parameterKey: string, index: number) => void;
};

type TestModalManagerContract = {
    openTestModal: () => void;
    startTest: (duration: 'short' | 'long') => void;
    resetModal: () => void;
    copyLogs: () => void;
    toggleLogsCollapse: () => void;
};

interface ModelDetailEventDependencies extends PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost, PageLifecycleOwnerHost, PageUiOwnerHost {
    session: ModelDetailSession;
    router: RouterContract | null;
    parameterView: ParameterViewContract;
    storage: PageControlsStorageInput;
    testModalManager: TestModalManagerContract;
    handleSwitchToParametersAction: () => void;
    modalPresenter: ModalPresenterApi;
    ensureUi: () => ModelDetailUi;
    requireModelId: () => string;
    streamManager: StreamRuntimeOwners;
    api: {
        models: {
            deleteAlias: (modelId: string) => Promise<SuccessfulMutationResponse>;
            updateAlias: (modelId: string, payload: { displayName: string; description: string | null }) => Promise<SuccessfulMutationResponse>;
        };
    };
}

const readRequiredActionParameter = (element: HTMLElement): string => {
    const value = element.dataset['param'];
    if (!value) {
        throw new Error('ModelDetailPage action requires data-param');
    }
    return value;
};

const readRequiredActionIndex = (element: HTMLElement): number => {
    const rawIndex = element.dataset['index'];
    if (!rawIndex) {
        throw new Error('ModelDetailPage action requires data-index');
    }
    const index = Number(rawIndex);
    if (!Number.isInteger(index) || index < 0) {
        throw new Error('ModelDetailPage array item action requires a non-negative data-index');
    }
    return index;
};

const createModelDetailDelegatedActionHandlers = (dependencies: { host: ModelDetailEventDependencies; view: ModelDetailViewHost; actionsHost: ModelDetailActionsHost; operationsHost: ModelDetailOperationsHost; save: { requestSave: () => Promise<void> } }) => {
    const { host, view, actionsHost, operationsHost } = dependencies;
    const signal = host.session.listeners?.signal;
    if (!signal) {
        throw new Error('ModelDetailPage delegated action handlers require an AbortController');
    }
    const renameModelModalRoot = host.modalPresenter.requireElement(MODELS_RENAME_MODEL_MODAL_ID);
    const renameModelModalManager = new RenameModelModalManager({
        host: {
            modals: host.modalPresenter,
            requireHTMLElement: (selector: string | Element, context?: Element): HTMLElement => {
                const scopeRoot = context ?? renameModelModalRoot;
                const resolved = typeof selector === 'string' ? dom.resolve(selector, scopeRoot) : selector;
                const selectorLabel = typeof selector === 'string' ? selector : selector.nodeName;
                if (!(resolved instanceof HTMLElement)) {
                    throw new Error(`ModelDetail rename modal missing HTMLElement: ${selectorLabel}`);
                }
                return resolved;
            },
            optionalHTMLElement: (selector: string | Element, context?: Element): HTMLElement | null => {
                const scopeRoot = context ?? renameModelModalRoot;
                const resolved = typeof selector === 'string' ? dom.resolve(selector, scopeRoot) : selector;
                return resolved instanceof HTMLElement ? resolved : null;
            },
            showNotification: (message: string, type: NotificationType, duration?: number): void => host.feedback.show(message, type, duration),
            runWithBoundary: <T>(operation: string, task: () => Promise<T>): Promise<T> => host.pageLifecycle.run(operation, task),
            updateText: (element: Element, text: string): void => host.pageDom.updateText(element, text),
            setUIValue: (target: Element, value: string, options?: { attribute?: string; skipChangeEvent?: boolean }): void => host.pageElements.setValue(target, value, options),
            refreshModelsCollection: async (): Promise<void> => {
                await host.streamManager.resources.refresh(MODELS, { throwOnError: true });
            },
            modelActions: {
                updateAlias: (universalId: string, payload: { displayName: string; description: string | null }): Promise<SuccessfulMutationResponse> => host.api.models.updateAlias(universalId, payload),
                removeAlias: (universalId: string): Promise<SuccessfulMutationResponse> => host.api.models.deleteAlias(universalId)
            }
        }
    });
    const handleAbort = (): void => {
        renameModelModalManager.disposeForPageDestroy();
        host.modalPresenter.close(MODELS_RENAME_MODEL_MODAL_ID, { force: true, restoreFocus: false, reason: 'abort' });
    };
    const handleRenameModelModalClose = (): void => renameModelModalManager.onModalClosed();
    renameModelModalRoot.addEventListener('core.modal.close', handleRenameModelModalClose, { signal });
    signal.addEventListener('abort', handleAbort, { once: true });
    return createModelDetailActionHandlers({
        navigation: {
            goBackToModels: () => {
                if (!host.router) {
                    throw new Error('ModelDetailPage requires router for navigation');
                }
                host.router.navigate('models');
            },
            switchToParameters: () => host.handleSwitchToParametersAction(),
            openBackendDocumentation: () => {
                terminateHandledPromise(handleModelDetailBackendDocumentationClick(view));
            }
        },
        model: {
            saveParameters: () => {
                terminateHandledPromise(dependencies.save.requestSave());
            },
            resetAllParameters: () => {
                terminateHandledPromise(resetAllModelDetailParameters(actionsHost));
            },
            manageAlias: () => {
                const model = host.session.model;
                if (!model) {
                    throw new Error('ModelDetail rename action requires a loaded model');
                }
                renameModelModalManager.showRenameModal(model);
            },
            openTestModal: () => host.testModalManager.openTestModal(),
            editVirtualModel: () => {
                if (!host.router?.navigateWithQuery) {
                    throw new Error('ModelDetailPage requires router query navigation for virtual model editing');
                }
                const virtualModelName = host.session.model?.name || host.session.model?.id;
                if (!virtualModelName) {
                    throw new Error('ModelDetailPage virtual model edit requires a model name');
                }
                host.router.navigateWithQuery('models', {
                    action: MODELS_ACTION_MANAGE_VIRTUAL_MODELS,
                    vm: virtualModelName
                });
            },
            deleteModel: () => {
                terminateHandledPromise(deleteModelDetailModel(operationsHost));
            },
            stopPlugin: () => {
                terminateHandledPromise(stopModelDetailPlugin(operationsHost));
            },
            toggleModelEnabled: (_event: Event, element: HTMLElement) => {
                terminateHandledPromise(toggleModelDetailEnabled(actionsHost, element));
            }
        },
        test: {
            startShortTest: () => {
                void host.testModalManager.startTest('short');
            },
            startLongTest: () => {
                void host.testModalManager.startTest('long');
            },
            stopPluginFromTest: () => {
                terminateHandledPromise(stopModelDetailPlugin(operationsHost));
            },
            resetTest: () => host.testModalManager.resetModal(),
            copyTestLogs: () => host.testModalManager.copyLogs(),
            toggleTestLogs: () => host.testModalManager.toggleLogsCollapse()
        },
        capabilities: {
            toggleOpenAICapability: (_event: Event, element: HTMLElement) => {
                void toggleModelDetailOpenAICapabilityOverride(actionsHost, element);
            },
            resetOpenAICapabilities: () => {
                terminateHandledPromise(resetModelDetailOpenAICapabilityOverrides(actionsHost));
            }
        },
        parameters: {
            addParameterArrayItem: (element: HTMLElement) => {
                host.parameterView.addArrayItem(readRequiredActionParameter(element));
            },
            removeParameterArrayItem: (element: HTMLElement) => {
                host.parameterView.removeArrayItem(readRequiredActionParameter(element), readRequiredActionIndex(element));
            }
        }
    });
};

const bindModelDetailAuxEventListeners = (dependencies: { host: Pick<ModelDetailEventDependencies, 'parameterView' | 'storage' | 'pageDom'> & Parameters<typeof handleModelDetailLanguageChanged>[1]; session: ModelDetailSession; ui: ModelDetailUi; signal: AbortSignal }): void => {
    const { host, ui, signal } = dependencies;
    ui.parameterUnifiedFilter.addEventListener(
        'change',
        (event: Event) => {
            event.preventDefault();
            host.parameterView.handleFilterSelection(ui.parameterUnifiedFilter.value);
            persistModelDetailParameterFilter(host.storage, ui.parameterUnifiedFilter.value);
        },
        { signal }
    );
    const handleSoaiLanguageChanged = (): void => terminateHandledPromise(handleModelDetailLanguageChanged(dependencies.session, host));
    getWindow().addEventListener('soai:language:changed', handleSoaiLanguageChanged, { signal });
};

export { bindModelDetailAuxEventListeners, createModelDetailDelegatedActionHandlers };
export type { ModelDetailEventDependencies };
