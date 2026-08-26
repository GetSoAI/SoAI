/* SoAI - Models page deletion controller [frontend/assets/ts/pages/models/controllers/page/modelsDeletionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modelsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import type { DeleteModelDependencies } from '@pages/models/controllers/modelsOperationsController.ts';
import type { ModelsPageModelActions } from '@pages/models/controllers/page/contracts.ts';
import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ModelsDeleteModelProperties {
    getModelPlugin(model: ResourceIncomingValue | null | undefined): string;
    isExternalProviderModel(model: ResourceIncomingValue | null | undefined): boolean;
}

interface ModelsDeleteVirtualModels {
    deleteVirtualModel(vmName: string): Promise<void>;
}

interface ModelsDeleteDependencies {
    collections: PageCollections;
    pageDom: PageDom;
    modelActions: Pick<ModelsPageModelActions, 'delete'>;
    getCardModelId(element: HTMLElement): string | null;
    executeItemDeletion(config: Parameters<DeleteModelDependencies['executeItemDeletion']>[0]): Promise<void>;
}

const createModelsDeleteDependencies = (dependencies: ModelsDeleteDependencies, modelProperties: ModelsDeleteModelProperties, virtualModelsManager: ModelsDeleteVirtualModels): DeleteModelDependencies => {
    return {
        getModelPlugin: (model) => modelProperties.getModelPlugin(model),
        isExternalProviderModel: (model) => modelProperties.isExternalProviderModel(model),
        getCollectionItem: (identifier) => (dependencies.collections.runtime ? dependencies.collections.runtime.find(identifier) : null),
        deleteVirtualModel: (vmName) => virtualModelsManager.deleteVirtualModel(vmName),
        executeItemDeletion: (config) => dependencies.executeItemDeletion(config),
        modelActionsDelete: (identifier) => dependencies.modelActions.delete(identifier),
        gridId: modelsPageConfig.grid.gridId,
        findCard: (grid, id) => {
            for (const candidate of dependencies.pageDom.query(modelsPageConfig.grid.cardSelector, grid ?? undefined)) {
                if (candidate instanceof HTMLElement && dependencies.getCardModelId(candidate) === id) {
                    return candidate;
                }
            }
            return null;
        }
    };
};

export { createModelsDeleteDependencies };
export type { ModelsDeleteDependencies, ModelsDeleteModelProperties, ModelsDeleteVirtualModels };
