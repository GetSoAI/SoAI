/* SoAI - Models page modal lifecycle controller [frontend/assets/ts/pages/models/controllers/page/modelsModalLifecycleController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { MODELS_ACTION_ADD_PROVIDER, MODELS_ACTION_DELETE_PROVIDER } from '@core/models/pageActions.ts';
import { bindManagedModalLifecycleEvents, createManagedModalCloseBinding } from '@core/modals/managedModalLifecycle.ts';

import { MODELS_DOWNLOAD_MODAL_ID, MODELS_EDIT_MODEL_MODAL_ID, MODELS_PROVIDERS_MODAL_ID, MODELS_RENAME_MODEL_MODAL_ID, MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, MODELS_VIRTUAL_MODELS_MODAL_ID } from '@features/models/public.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';

type ProvidersModalActionId = typeof MODELS_ACTION_ADD_PROVIDER | typeof MODELS_ACTION_DELETE_PROVIDER;

interface ModalLifecycleManager {
    onModalClosed(): void;
    disposeForPageDestroy(): void;
}

interface DownloadModalLifecycleManager extends ModalLifecycleManager {
    bindModalEventListeners(signal: AbortSignal): void;
    openProviderTab(event?: Event): void;
}

interface ProvidersModalLifecycleManager extends ModalLifecycleManager {
    closeProvidersModal(event?: Event): void;
    handleProviderDelete(event: Event, button: Element): Promise<void>;
}

interface VirtualModelsLifecycleManager extends ModalLifecycleManager {
    onVmEditModalClosed(): void;
}

interface ModelsModalLifecycleManagers {
    downloadModalManager: DownloadModalLifecycleManager;
    editModelModalManager: ModalLifecycleManager;
    renameModelModalManager: ModalLifecycleManager;
    providersManager: ProvidersModalLifecycleManager;
    virtualModelsManager: VirtualModelsLifecycleManager;
}

const isProvidersModalActionId = (value: string | undefined): value is ProvidersModalActionId => {
    return value === MODELS_ACTION_ADD_PROVIDER || value === MODELS_ACTION_DELETE_PROVIDER;
};

const bindProvidersModalActions = (host: PageServicesOwnerHost, signal: AbortSignal, managers: ModelsModalLifecycleManagers): void => {
    bindPageActionDispatcher({
        label: 'Models providers modal',
        root: host.services.modals.requireElement(MODELS_PROVIDERS_MODAL_ID),
        signal,
        isAction: isProvidersModalActionId,
        events: {
            click: {
                mouseButton: 'primary',
                preventDefault: 'interactive',
                ignoreDisabled: true,
                stopPropagation: true,
                onAction: ({ event, action, actionElement }): void | Promise<void> => {
                    if (action === MODELS_ACTION_DELETE_PROVIDER) {
                        return managers.providersManager.handleProviderDelete(event, actionElement);
                    }
                    managers.providersManager.closeProvidersModal(event);
                    managers.downloadModalManager.openProviderTab(event);
                    return undefined;
                }
            }
        }
    });
};

const bindModelsModalLifecycleEvents = (host: PageServicesOwnerHost, signal: AbortSignal, managers: ModelsModalLifecycleManagers): void => {
    managers.downloadModalManager.bindModalEventListeners(signal);
    bindProvidersModalActions(host, signal, managers);
    bindManagedModalLifecycleEvents({
        signal,
        resolveModalElement: (modalId) => host.services.modals.requireElement(modalId),
        bindings: [
            createManagedModalCloseBinding(MODELS_DOWNLOAD_MODAL_ID, managers.downloadModalManager),
            createManagedModalCloseBinding(MODELS_EDIT_MODEL_MODAL_ID, managers.editModelModalManager),
            createManagedModalCloseBinding(MODELS_RENAME_MODEL_MODAL_ID, managers.renameModelModalManager),
            createManagedModalCloseBinding(MODELS_PROVIDERS_MODAL_ID, managers.providersManager),
            createManagedModalCloseBinding(MODELS_VIRTUAL_MODELS_MODAL_ID, managers.virtualModelsManager),
            {
                modalId: MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID,
                onModalClosed: () => managers.virtualModelsManager.onVmEditModalClosed()
            }
        ]
    });
};

export { bindModelsModalLifecycleEvents };
