/* SoAI - Models page persisted filter and sorting hydration [frontend/assets/ts/pages/models/widgets/modelsPageFilterControls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requirePageControlsStorage, type PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import type { ModelsPageControlState } from '@core/storage/types.ts';
import { normalizeModelsSortState } from '@pages/models/controllers/page/listSortingController.ts';

interface ModelsFilterStateHost {
    filterProvider: string;
    filterStatus: string;
    sortBy: string;
    sortOrder: 'asc' | 'desc' | null;
    searchQuery: string;
    storage: PageControlsStorageInput;
}

const getSavedModelsPageControls = (storage: PageControlsStorageInput): ModelsPageControlState => requirePageControlsStorage(storage).getPageControlState('models');

const applySavedModelsFilters = (host: ModelsFilterStateHost): void => {
    const savedControls = getSavedModelsPageControls(host.storage);
    const sort = normalizeModelsSortState(savedControls);
    host.filterProvider = savedControls.filterProvider || 'all';
    host.filterStatus = 'all';
    host.sortBy = sort.column;
    host.sortOrder = sort.direction;
    host.searchQuery = '';
    if (sort.column !== savedControls.sortBy || sort.direction !== savedControls.sortOrder) {
        requirePageControlsStorage(host.storage).setPageControlState('models', { sortBy: sort.column, sortOrder: sort.direction });
    }
};

export { applySavedModelsFilters, getSavedModelsPageControls };
export type { ModelsFilterStateHost };
