/* SoAI - Models page grouping controller [frontend/assets/ts/pages/models/controllers/modelsGroupingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionGroupingState, CollectionGroupResolution } from '@core/collectionpage/collectionGroupingState.ts';
import { resolveAlphabeticGroupKey } from '@core/primitives/grouping.ts';
import { normalizeSortFilterValue } from '@core/primitives/sort.ts';
import { isArray } from '@core/typeGuards.ts';
import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { getSortValue, isModelRecord, resolveGroupHeading, type ModelPropertyInput } from '@pages/models/controllers/modelsModelProperties.ts';

interface ModelsGroupingControllerDependencies {
    grouping: CollectionGroupingState<ModelRecord>;
    getSortBy: () => string;
    getItemCardId: (item: ResourceIncomingValue | null | undefined) => string | number | null;
    getPluginByName: (name: string) => PluginRecord | null;
    statusManager: { getDescription(status: string): string };
    getModelPlugin: (model: ModelPropertyInput) => string;
    getModelProvider: (model: ModelPropertyInput) => string;
    getModelStatus: (model: ModelPropertyInput) => string;
    getModelDisplayName: (model: ModelPropertyInput) => string;
}

interface ModelsGroupingController {
    normalizeSortBy: (value: string | null | undefined) => string;
    getNameGroupKey: (name: string | null | undefined) => string | null;
    getSortValue: (model: ResourceIncomingValue | null | undefined, field: string) => string | number;
    preparePresentation: (models: ReadonlyArray<ModelRecord>) => string[];
}

const UNGROUPED_SORT_KEYS: ReadonlySet<string> = new Set<string>(['none']);

const createModelsGroupingController = (dependencies: ModelsGroupingControllerDependencies): ModelsGroupingController => {
    const normalizeSortBy = (value: string | null | undefined): string => {
        const allowed = ['none', 'name', 'type', 'provider', 'plugin', 'status', 'size'];
        return normalizeSortFilterValue(value, allowed, 'none');
    };

    const computeSortValue = (model: ResourceIncomingValue | null | undefined, field: string): string | number => {
        return getSortValue({
            model,
            field,
            getModelPlugin: dependencies.getModelPlugin,
            getModelProvider: dependencies.getModelProvider,
            getModelStatus: dependencies.getModelStatus,
            getModelDisplayName: dependencies.getModelDisplayName
        });
    };

    const resolveModelGroup = (model: ModelRecord, sortBy: string): CollectionGroupResolution => {
        if (!isModelRecord(model)) return { key: null, heading: null };
        return resolveGroupHeading({
            model,
            sortKey: sortBy,
            getModelPlugin: dependencies.getModelPlugin,
            getModelProvider: dependencies.getModelProvider,
            getModelStatus: dependencies.getModelStatus,
            getModelDisplayName: dependencies.getModelDisplayName,
            getNameGroupKey: resolveAlphabeticGroupKey,
            getPluginByName: dependencies.getPluginByName,
            statusManager: dependencies.statusManager
        });
    };

    const applyHeadings = (models: ReadonlyArray<ModelRecord>): string[] => {
        const sortBy = dependencies.getSortBy();
        return dependencies.grouping.applyHeadings({
            items: isArray(models) ? models : [],
            grouped: Boolean(sortBy) && !UNGROUPED_SORT_KEYS.has(sortBy),
            resolveItemId: (model) => {
                const identifier = dependencies.getItemCardId(model);
                return identifier === null ? '' : String(identifier);
            },
            resolveGroup: (model) => resolveModelGroup(model, sortBy)
        });
    };

    return {
        normalizeSortBy,
        getNameGroupKey: resolveAlphabeticGroupKey,
        getSortValue: computeSortValue,
        preparePresentation: applyHeadings
    };
};

export { createModelsGroupingController };
export type { ModelsGroupingController, ModelsGroupingControllerDependencies };
