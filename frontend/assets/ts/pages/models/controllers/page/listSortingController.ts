/* SoAI - Models page shared sorting control and list behavior [frontend/assets/ts/pages/models/controllers/page/listSortingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceItem } from '@core/data/ClientDataHub.ts';
import { i18n } from '@core/i18n/index.ts';
import { requirePageControlsStorage, type PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { ModelsPageControlState } from '@core/storage/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { normalizeStoredSortState, requireSortableColumn, type SortDirection, type SortState } from '@core/ui/tables/sortableTable.ts';
import { applySortControlSelection, sortCollectionListFromHeader, syncSortControl, syncSortableListIndicators, type SortControlDefinition } from '@core/uiprimitives/sortableList.ts';
import { getModelDisplayName, getModelPlugin, getModelProvider, getModelStatus, getSortValue, isModelRecord } from '@pages/models/controllers/modelsModelProperties.ts';

type ModelsSortColumn = 'none' | 'name' | 'type' | 'provider' | 'plugin' | 'size' | 'status';
type ModelsListSortColumn = Exclude<ModelsSortColumn, 'none'>;

const MODELS_SORT_COLUMNS: readonly ModelsSortColumn[] = ['none', 'name', 'type', 'provider', 'plugin', 'size', 'status'];
const MODELS_LIST_SORT_COLUMNS: readonly ModelsListSortColumn[] = ['name', 'type', 'provider', 'plugin', 'size', 'status'];
const MODELS_SORT_DEFAULT_DIRECTIONS: Record<ModelsSortColumn, SortDirection> = {
    none: 'asc',
    name: 'asc',
    type: 'asc',
    provider: 'asc',
    plugin: 'asc',
    size: 'desc',
    status: 'asc'
};

interface ModelsListSortHost extends PageServicesOwnerHost, PageUiOwnerHost, PageDomOwnerHost {
    sortBy: string | null;
    sortOrder: SortDirection | null;
    filterProvider: string | null;
    storage: PageControlsStorageInput;
}

const normalizeModelsSortState = (state: Pick<ModelsPageControlState, 'sortBy' | 'sortOrder'>): SortState<ModelsSortColumn> => {
    return normalizeStoredSortState({ state: { column: state.sortBy, direction: state.sortOrder }, columns: MODELS_SORT_COLUMNS, fallback: { column: 'none', direction: 'asc' }, defaultDirections: MODELS_SORT_DEFAULT_DIRECTIONS });
};

const createModelsSortControlDefinition = (state: SortState<ModelsSortColumn>): SortControlDefinition<ModelsSortColumn> => ({
    id: 'models-sort',
    className: 'page-header-filter-select models-sort',
    shellClassName: 'page-header-filter-select-shell',
    state,
    prefix: i18n.t('common.filters.sortBy'),
    ascendingLabel: i18n.t('common.sorting.ascending'),
    descendingLabel: i18n.t('common.sorting.descending'),
    inactiveColumn: 'none',
    options: [
        { column: 'none', label: i18n.t('common.sorting.none'), standaloneSelectionLabel: true },
        { column: 'name', label: i18n.t('models.sort.byName') },
        { column: 'type', label: i18n.t('models.sort.byType') },
        { column: 'provider', label: i18n.t('models.sort.byProvider') },
        { column: 'plugin', label: i18n.t('models.sort.byPlugin') },
        { column: 'status', label: i18n.t('models.sort.byStatus') },
        { column: 'size', label: i18n.t('models.sort.bySize') }
    ]
});

const persistModelsSort = (storage: PageControlsStorageInput, state: SortState<ModelsSortColumn>): void => {
    requirePageControlsStorage(storage).setPageControlState('models', { sortBy: state.column, sortOrder: state.direction });
};

const persistModelsProviderFilter = (storage: PageControlsStorageInput, filterProvider: string): void => {
    requirePageControlsStorage(storage).setPageControlState('models', { filterProvider });
};

const getModelsListSortValue = (host: { stateManager: { status: { normalizeStatus(status: JsonValue | null | undefined): string } } }, model: ResourceItem | null | undefined, field: string): string | number => {
    if (!isModelRecord(model)) return '';
    return getSortValue({
        model,
        field,
        getModelPlugin: (item) => getModelPlugin(item),
        getModelProvider: (item) => getModelProvider(item),
        getModelStatus: (item) => getModelStatus(host.stateManager.status, item),
        getModelDisplayName: (item) => getModelDisplayName(item)
    });
};

const syncModelsSortControls = (host: ModelsListSortHost): void => {
    const state = normalizeModelsSortState({ sortBy: host.sortBy ?? 'none', sortOrder: host.sortOrder ?? 'asc' });
    const select = host.pageDom.optionalHTMLElement('models-sort');
    if (select) {
        if (!(select instanceof HTMLSelectElement)) throw new TypeError('Models sort control must be an HTMLSelectElement');
        syncSortControl(select, createModelsSortControlDefinition(state));
    }
    const table = host.pageDom.optional('.models-list-table');
    if (table) syncSortableListIndicators(host, table, 'Models');
};

const applyModelsSortSelection = (host: ModelsListSortHost, requestedColumn: string, reapplyCollection: (options: { shouldRender: boolean; updateStats: boolean; updateFilters: boolean; resetScroll: boolean }) => void): void => {
    const column = requireSortableColumn(MODELS_SORT_COLUMNS, requestedColumn, 'Models');
    applySortControlSelection({
        requestedColumn: column,
        host,
        columns: MODELS_SORT_COLUMNS,
        defaultDirections: MODELS_SORT_DEFAULT_DIRECTIONS,
        inactiveColumn: 'none',
        reapplyCollection,
        afterSort: (nextColumn, direction) => {
            persistModelsSort(host.storage, { column: nextColumn, direction });
            syncModelsSortControls(host);
        }
    });
};

const sortModelsListFromHeader = (host: ModelsListSortHost, actionElement: HTMLElement, reapplyCollection: (options: { shouldRender: boolean; updateStats: boolean; updateFilters: boolean; resetScroll: boolean }) => void): void => {
    sortCollectionListFromHeader({
        actionElement,
        host,
        columns: MODELS_LIST_SORT_COLUMNS,
        defaultDirections: MODELS_SORT_DEFAULT_DIRECTIONS,
        context: 'Models',
        reapplyCollection,
        afterSort: (column, direction) => {
            persistModelsSort(host.storage, { column, direction });
            syncModelsSortControls(host);
        }
    });
};

const syncModelsListSortIndicators = (host: PageServicesOwnerHost & Pick<ModelsListSortHost, 'sortBy' | 'sortOrder'>, table: Element): void => {
    syncSortableListIndicators(host, table, 'Models');
};

export { applyModelsSortSelection, createModelsSortControlDefinition, getModelsListSortValue, normalizeModelsSortState, persistModelsProviderFilter, sortModelsListFromHeader, syncModelsListSortIndicators, syncModelsSortControls };
export type { ModelsListSortHost, ModelsSortColumn };
