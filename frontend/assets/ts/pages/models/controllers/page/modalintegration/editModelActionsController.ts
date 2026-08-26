/* SoAI - Models page edit model actions controller [frontend/assets/ts/pages/models/controllers/page/modalintegration/editModelActionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { MODELS_RENAME_MODEL_MODAL_ID, RenameModelModalManager } from '@features/models/public.ts';
import { createModelsDeleteController } from '@pages/models/controllers/modelsOperationsController.ts';
import { resolveModelsItemCardId, type ModelPropertyInput } from '@pages/models/controllers/modelsModelProperties.ts';
import type { ModelsModalRuntimeDependencies } from '@pages/models/controllers/page/contracts.ts';
import { createModelsDeleteDependencies } from '@pages/models/controllers/page/modelsDeletionController.ts';
import { createModelsItemDeletionHost, executeModelsItemDeletion } from '@pages/models/controllers/page/service.ts';

interface EditModelActionModelProperties {
    getModelPlugin(model: ModelPropertyInput): string;
    isExternalProviderModel(model: ModelPropertyInput): boolean;
}

interface EditModelActionVirtualModels {
    deleteVirtualModel(vmName: string): Promise<void>;
}

interface EditModelActionBridge {
    renameModelModalManager: RenameModelModalManager;
    showRenameModelModal(model: ModelRecord): void;
    deleteModel(model: ModelRecord): Promise<void>;
}

const resolveEditActionModelIdentifier = (model: ModelRecord): string => {
    const universalId = toTrimmedStringOrNull(model.universalId);
    if (universalId) {
        return universalId;
    }
    const itemId = toTrimmedStringOrNull(resolveModelsItemCardId(model));
    if (!itemId) {
        throw new Error('Edit model action requires a model identifier');
    }
    return itemId;
};

const createEditModelActionBridge = (runtime: ModelsModalRuntimeDependencies, modelProperties: EditModelActionModelProperties, virtualModelsManager: EditModelActionVirtualModels): EditModelActionBridge => {
    const { infrastructure, collection, session } = runtime;
    const renameModelModalRoot = infrastructure.services.modals.requireElement(MODELS_RENAME_MODEL_MODAL_ID);
    const renameModelModalManager = new RenameModelModalManager({
        host: {
            modals: infrastructure.services.modals,
            requireHTMLElement: (selector, context) => infrastructure.pageDom.requireHTMLElement(selector, context ?? renameModelModalRoot),
            optionalHTMLElement: (selector, context) => infrastructure.pageDom.optionalHTMLElement(selector, context ?? renameModelModalRoot),
            setUIValue: (target, value, options) => infrastructure.pageElements.setValue(target, value, options),
            showNotification: (message, type, options) => infrastructure.feedback.show(message, type, options),
            runWithBoundary: (name, task) => infrastructure.pageLifecycle.run(name, task),
            updateText: (target, text) => infrastructure.pageDom.updateText(target, text),
            refreshModelsCollection: async () => {
                await infrastructure.streaming.runtime().resources.refresh(MODELS, { allowDiscovery: true, throwOnError: true });
            },
            modelActions: runtime.modelActions
        }
    });
    const deleteModelById = createModelsDeleteController(
        createModelsDeleteDependencies(
            {
                collections: collection.collections,
                pageDom: infrastructure.pageDom,
                modelActions: runtime.modelActions,
                getCardModelId: (element) => infrastructure.dom.getData(element, 'model'),
                executeItemDeletion: async (config) => {
                    await executeModelsItemDeletion(
                        createModelsItemDeletionHost({
                            deletingItems: session.deletingItems,
                            streams: infrastructure.streaming.pageTracker,
                            pageDom: infrastructure.pageDom,
                            feedback: infrastructure.feedback,
                            renderItems: collection.renderItems,
                            removeItemById: (id) => collection.removeItemById(id)
                        }),
                        config
                    );
                }
            },
            modelProperties,
            virtualModelsManager
        )
    );
    return {
        renameModelModalManager,
        showRenameModelModal: (model) => renameModelModalManager.showRenameModal(model),
        deleteModel: async (model) => await deleteModelById(resolveEditActionModelIdentifier(model))
    };
};

export { createEditModelActionBridge };
export type { EditModelActionBridge, EditModelActionModelProperties, EditModelActionVirtualModels };
