/* SoAI - Plugins page shared sorting control and list behavior [frontend/assets/ts/pages/plugins/controllers/page/listSortingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { normalizeSortFilterValue } from '@core/primitives/sort.ts';
import { requirePageControlsStorage, type PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PluginsPageControlState } from '@core/storage/types.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { normalizeStoredSortState, requireSortableColumn, type SortDirection, type SortState } from '@core/ui/tables/sortableTable.ts';
import { applySortControlSelection, sortCollectionListFromHeader, syncSortControl, syncSortableListIndicators, type SortControlDefinition } from '@core/uiprimitives/sortableList.ts';

type PluginsSortColumn = 'none' | 'name' | 'models' | 'status';
type PluginsListSortColumn = Exclude<PluginsSortColumn, 'none'>;

const PLUGINS_SORT_COLUMNS: readonly PluginsSortColumn[] = ['none', 'name', 'models', 'status'];
const PLUGINS_LIST_SORT_COLUMNS: readonly PluginsListSortColumn[] = ['name', 'models', 'status'];
const PLUGINS_SORT_DEFAULT_DIRECTIONS: Record<PluginsSortColumn, SortDirection> = {
    none: 'asc',
    name: 'asc',
    models: 'desc',
    status: 'asc'
};

interface PluginsListSortHost extends PageServicesOwnerHost, PageUiOwnerHost, PageDomOwnerHost {
    sortBy: string | null;
    sortOrder: SortDirection | null;
    storage: PageControlsStorageInput;
}

interface PluginsPageControlHost {
    filterProvider: string;
    filterStatus: string;
    sortBy: string | null;
    sortOrder: SortDirection | null;
    searchQuery: string;
    storage: PageControlsStorageInput;
}

const normalizePluginsSortState = (state: Pick<PluginsPageControlState, 'sortBy' | 'sortOrder'>): SortState<PluginsSortColumn> => {
    return normalizeStoredSortState({ state: { column: state.sortBy, direction: state.sortOrder }, columns: PLUGINS_SORT_COLUMNS, fallback: { column: 'none', direction: 'asc' }, defaultDirections: PLUGINS_SORT_DEFAULT_DIRECTIONS });
};

const createPluginsSortControlDefinition = (state: SortState<PluginsSortColumn>): SortControlDefinition<PluginsSortColumn> => ({
    id: 'plugins-sort',
    className: 'page-header-filter-select plugins-sort',
    shellClassName: 'page-header-filter-select-shell',
    state,
    prefix: i18n.t('common.filters.sortBy'),
    ascendingLabel: i18n.t('common.sorting.ascending'),
    descendingLabel: i18n.t('common.sorting.descending'),
    inactiveColumn: 'none',
    options: [
        { column: 'none', label: i18n.t('common.sorting.none'), standaloneSelectionLabel: true },
        { column: 'name', label: i18n.t('plugins.sort.name') },
        { column: 'models', label: i18n.t('plugins.sort.models') },
        { column: 'status', label: i18n.t('plugins.sort.status') }
    ]
});

const persistPluginsSort = (storage: PageControlsStorageInput, state: SortState<PluginsSortColumn>): void => {
    requirePageControlsStorage(storage).setPageControlState('plugins', { sortBy: state.column, sortOrder: state.direction });
};

const persistPluginsFilter = (storage: PageControlsStorageInput, property: 'filterProvider' | 'filterStatus', value: string): void => {
    requirePageControlsStorage(storage).setPageControlState('plugins', { [property]: value });
};

const hydratePluginsPageControls = (host: PluginsPageControlHost): void => {
    const storage = requirePageControlsStorage(host.storage);
    const saved = storage.getPageControlState('plugins');
    const filterProvider = normalizeSortFilterValue(saved.filterProvider, ['all', 'active', 'inactive'], 'all');
    const filterStatus = normalizeSortFilterValue(saved.filterStatus, ['all', 'builtin', 'thirdparty'], 'all');
    const sort = normalizePluginsSortState(saved);
    host.filterProvider = filterProvider;
    host.filterStatus = filterStatus;
    host.sortBy = sort.column;
    host.sortOrder = sort.direction;
    host.searchQuery = '';
    const correction: Partial<PluginsPageControlState> = {};
    if (saved.filterProvider !== filterProvider) correction.filterProvider = filterProvider;
    if (saved.filterStatus !== filterStatus) correction.filterStatus = filterStatus;
    if (saved.sortBy !== sort.column) correction.sortBy = sort.column;
    if (saved.sortOrder !== sort.direction) correction.sortOrder = sort.direction;
    if (Object.keys(correction).length > 0) storage.setPageControlState('plugins', correction);
};

const getPluginsListSortValue = (plugin: PluginRecord, field: string, getStatus: (plugin: PluginRecord) => string): string | number => {
    if (field === 'models') return plugin.stats?.modelCount ?? 0;
    if (field === 'status') return getStatus(plugin);
    return toTrimmedString(plugin.displayName) || toTrimmedString(plugin.name);
};

const syncPluginsSortControls = (host: PluginsListSortHost): void => {
    const state = normalizePluginsSortState({ sortBy: host.sortBy ?? 'none', sortOrder: host.sortOrder ?? 'asc' });
    const select = host.pageDom.optionalHTMLElement('plugins-sort');
    if (select) {
        if (!(select instanceof HTMLSelectElement)) throw new TypeError('Plugins sort control must be an HTMLSelectElement');
        syncSortControl(select, createPluginsSortControlDefinition(state));
    }
    const table = host.pageDom.optional('.plugins-list-table');
    if (table) syncSortableListIndicators(host, table, 'Plugins');
};

const applyPluginsSortSelection = (host: PluginsListSortHost, requestedColumn: string, reapplyCollection: (options: { shouldRender: boolean; updateStats: boolean; updateFilters: boolean; resetScroll: boolean }) => void): void => {
    const column = requireSortableColumn(PLUGINS_SORT_COLUMNS, requestedColumn, 'Plugins');
    applySortControlSelection({
        requestedColumn: column,
        host,
        columns: PLUGINS_SORT_COLUMNS,
        defaultDirections: PLUGINS_SORT_DEFAULT_DIRECTIONS,
        inactiveColumn: 'none',
        reapplyCollection,
        afterSort: (nextColumn, direction) => {
            persistPluginsSort(host.storage, { column: nextColumn, direction });
            syncPluginsSortControls(host);
        }
    });
};

const sortPluginsListFromHeader = (host: PluginsListSortHost, actionElement: HTMLElement, reapplyCollection: (options: { shouldRender: boolean; updateStats: boolean; updateFilters: boolean; resetScroll: boolean }) => void): void => {
    sortCollectionListFromHeader({
        actionElement,
        host,
        columns: PLUGINS_LIST_SORT_COLUMNS,
        defaultDirections: PLUGINS_SORT_DEFAULT_DIRECTIONS,
        context: 'Plugins',
        reapplyCollection,
        afterSort: (column, direction) => {
            persistPluginsSort(host.storage, { column, direction });
            syncPluginsSortControls(host);
        }
    });
};

const syncPluginsListSortIndicators = (host: PageServicesOwnerHost & Pick<PluginsListSortHost, 'sortBy' | 'sortOrder'>, table: Element): void => {
    syncSortableListIndicators(host, table, 'Plugins');
};

export { applyPluginsSortSelection, createPluginsSortControlDefinition, getPluginsListSortValue, hydratePluginsPageControls, normalizePluginsSortState, persistPluginsFilter, sortPluginsListFromHeader, syncPluginsListSortIndicators, syncPluginsSortControls };
export type { PluginsListSortHost, PluginsPageControlHost, PluginsSortColumn };
