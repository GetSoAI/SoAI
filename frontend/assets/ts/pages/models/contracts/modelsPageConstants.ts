/* SoAI - Models page constants [frontend/assets/ts/pages/models/contracts/modelsPageConstants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceItem } from '@core/data/ClientDataHub.ts';
import { getModelDisplayName, getModelOriginId, getModelPlugin, getModelProvider } from '@pages/models/controllers/modelsModelProperties.ts';

const PAGE_NAME = 'ModelsPage';
const PAGE_ID = 'models';
const PAGE_MODULE_ID = 'pages.ModelsPage';
const STR_ALL = 'all';
const STR_VIRTUAL = 'virtual';
const STR_NONE = 'none';

const MODEL_SEARCH_FIELD_RESOLVERS = Object.freeze({
    getModelDisplayName: (item: ResourceItem | null | undefined): string => getModelDisplayName(item),
    getModelOriginId: (item: ResourceItem | null | undefined): string => getModelOriginId(item),
    getModelPlugin: (item: ResourceItem | null | undefined): string => getModelPlugin(item),
    getModelProvider: (item: ResourceItem | null | undefined): string => getModelProvider(item)
});

export { MODEL_SEARCH_FIELD_RESOLVERS, PAGE_ID, PAGE_MODULE_ID, PAGE_NAME, STR_ALL, STR_NONE, STR_VIRTUAL };
