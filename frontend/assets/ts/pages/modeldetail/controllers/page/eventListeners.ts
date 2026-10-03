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
import type { ParameterGroup, ParameterView } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { isParameterGroup, isParameterView } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';
import { createModelDetailActionHandlers } from '@pages/modeldetail/controllers/modelDetailActionHandlers.ts';
import { resetModelDetailOpenAICapabilityOverrides, toggleModelDetailOpenAICapabilityOverride } from '@pages/modeldetail/controllers/openaicapabilities/overrideActions.ts';
import { resetAllModelDetailParameters, type ModelDetailActionsHost } from '@pages/modeldetail/controllers/page/actionEffects.ts';
import { handleModelDetailLanguageChanged } from '@pages/modeldetail/controllers/page/dom.ts';
import { deleteModelDetailModel, stopModelDetailPlugin } from '@pages/modeldetail/controllers/page/operations/effects.ts';
import { handleModelDetailBackendDocumentationClick } from '@pages/modeldetail/controllers/page/view/service.ts';
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
    addArrayItem: (parameterKey: string) => void;
    removeArrayItem: (parameterKey: string, index: number) => void;
    resetParameter: (parameterKey: string) => void;
    setView: (view: ParameterView) => void;
    toggleGroup: (group: ParameterGroup) => void;
    navigateToCategory: (category: string) => void;
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
    copyText: (value: string) => Promise<void>;
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

const requireActionData = (value: string | undefined, attribute: string): string => {
    if (!value) {
        throw new Error(`ModelDetailPage action requires ${attribute}`);
    }
    return value;
};

const readRequiredActionParameter = (element: HTMLElement): string => requireActionData(element.dataset['param'], 'data-param');

const readRequiredActionView = (element: HTMLElement): ParameterView => {
    const view = element.dataset['parameterView'];
    if (!isParameterView(view)) {
        throw new Error('ModelDetailPage parameter view action requires a known data-parameter-view');
    }
    return view;
};

const readRequiredActionGroup = (element: HTMLElement): ParameterGroup => {
    const group = element.dataset['parameterGroup'];
    if (!isParameterGroup(group)) {
        throw new Error('ModelDetailPage parameter group action requires a known data-parameter-group');
    }
    return group;
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
            },
            copyValue: (element: HTMLElement) => {
                const source = host.pageDom.optionalHTMLElement(requireActionData(element.dataset['copySource'], 'data-copy-source'));
                const value = (source?.dataset['copyValue'] ?? source?.textContent)?.trim();
                if (value) {
                    terminateHandledPromise(host.copyText(value));
                }
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
            },
            revertParameter: (element: HTMLElement) => {
                host.parameterView.resetParameter(readRequiredActionParameter(element));
            },
            selectParameterView: (element: HTMLElement) => {
                host.parameterView.setView(readRequiredActionView(element));
            },
            selectParameterGroup: (element: HTMLElement) => {
                host.parameterView.toggleGroup(readRequiredActionGroup(element));
            },
            navigateParameterCategory: (element: HTMLElement) => {
                host.parameterView.navigateToCategory(requireActionData(element.dataset['category'], 'data-category'));
            }
        }
    });
};

const bindModelDetailAuxEventListeners = (dependencies: { host: Parameters<typeof handleModelDetailLanguageChanged>[1]; session: ModelDetailSession; signal: AbortSignal }): void => {
    const { host, signal } = dependencies;
    const handleSoaiLanguageChanged = (): void => terminateHandledPromise(handleModelDetailLanguageChanged(dependencies.session, host));
    getWindow().addEventListener('soai:language:changed', handleSoaiLanguageChanged, { signal });
};

export { bindModelDetailAuxEventListeners, createModelDetailDelegatedActionHandlers };
export type { ModelDetailEventDependencies };
