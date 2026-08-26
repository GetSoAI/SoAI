/* SoAI - Models page state [frontend/assets/ts/pages/models/controllers/page/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeModelRecord } from '@core/models/modelRecordNormalization.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { isJsonValue } from '@core/types/jsonValues.ts';
import type { ResourceIncomingObject, ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import type { ModelData, ModelRecord } from '@core/types/modelTypes.ts';

const isResourceObject = (value: ResourceIncomingValue | null | undefined): value is ResourceIncomingObject => isObject(value);

const isModelData = (value: ResourceIncomingValue | null | undefined): value is ModelData => {
    if (!isResourceObject(value)) {
        return false;
    }
    return isString(value['id']) && isString(value['name']);
};

const normalizeModelRecordStrict = (item: ResourceIncomingValue | null | undefined, context: string): ModelRecord => {
    if (item === null || item === undefined) {
        throw new TypeError(`${context} requires a model record`);
    }
    const jsonItem = isJsonValue(item) ? item : toJsonCompatibleValue(item);
    const normalized = normalizeModelRecord(jsonItem);
    if (!normalized) {
        throw new TypeError(`${context} requires a valid model record`);
    }
    return normalized;
};

const getAllModels = (collection: { getAll(): ResourceItem[] }): ModelRecord[] => {
    const allItems = collection.getAll();
    const models: ModelRecord[] = [];
    for (const item of allItems) {
        models.push(normalizeModelRecordStrict(item, 'ModelsPage.getAllModels'));
    }
    return models;
};

const getFilteredModels = (collection: { getFiltered(): ResourceItem[] }): ModelRecord[] => {
    const filteredItems = collection.getFiltered();
    const models: ModelRecord[] = [];
    for (const item of filteredItems) {
        models.push(normalizeModelRecordStrict(item, 'ModelsPage.getFilteredModels'));
    }
    return models;
};

const getItemSearchFields = (
    model: ResourceItem | null | undefined,
    dependencies: {
        getModelDisplayName: (item: ResourceItem | null | undefined) => string;
        getModelOriginId: (item: ResourceItem | null | undefined) => string;
        getModelPlugin: (item: ResourceItem | null | undefined) => string;
        getModelProvider: (item: ResourceItem | null | undefined) => string;
    }
): string[] => {
    if (!isObject(model)) {
        return [];
    }
    const description = toTrimmedString(model['description']);
    const fields = [dependencies.getModelDisplayName(model), toTrimmedString(model['alias']), dependencies.getModelOriginId(model), dependencies.getModelPlugin(model), dependencies.getModelProvider(model), description];
    return fields.filter((field) => isString(field) && field.length > 0);
};

const matchesProviderFilter = (model: ResourceItem | null | undefined, filterProvider: string, getModelPlugin: (item: ResourceItem | null | undefined) => string): boolean => {
    const pluginName = getModelPlugin(model);
    if (filterProvider !== 'all' && pluginName !== filterProvider) {
        return false;
    }
    return true;
};

export { getAllModels, getFilteredModels, getItemSearchFields, isModelData, matchesProviderFilter, normalizeModelRecordStrict };
