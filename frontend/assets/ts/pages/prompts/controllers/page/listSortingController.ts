/* SoAI - Prompts page shared sorting control and list behavior [frontend/assets/ts/pages/prompts/controllers/page/listSortingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceItem } from '@core/data/ClientDataHub.ts';
import { i18n } from '@core/i18n/index.ts';
import { requirePageControlsStorage } from '@core/pagecontrols/storageController.ts';
import type { PromptsPageControlState } from '@core/storage/types.ts';
import type { ColorToolkitInterface } from '@pages/prompts/contracts/contracts.ts';
import type { PromptsRuntimeContext } from '@pages/prompts/controllers/page/contracts.ts';
import { normalizeStoredSortState, requireSortableColumn, type SortDirection, type SortState } from '@core/ui/tables/sortableTable.ts';
import { applySortControlSelection, sortCollectionListFromHeader, syncSortControl, syncSortableListIndicators, type SortControlDefinition } from '@core/uiprimitives/sortableList.ts';

type PromptsSortColumn = 'none' | 'date' | 'name' | 'color';
type PromptsListSortColumn = 'name' | 'date';

const PROMPTS_SORT_COLUMNS: readonly PromptsSortColumn[] = ['none', 'date', 'name', 'color'];
const PROMPTS_LIST_SORT_COLUMNS: readonly PromptsListSortColumn[] = ['name', 'date'];
const PROMPTS_SORT_DEFAULT_DIRECTIONS: Record<PromptsSortColumn, SortDirection> = { none: 'asc', date: 'desc', name: 'asc', color: 'asc' };

const normalizePromptsSortState = (state: Pick<PromptsPageControlState, 'sortBy' | 'sortOrder'>): SortState<PromptsSortColumn> => {
    return normalizeStoredSortState({ state: { column: state.sortBy, direction: state.sortOrder }, columns: PROMPTS_SORT_COLUMNS, fallback: { column: 'none', direction: 'asc' }, defaultDirections: PROMPTS_SORT_DEFAULT_DIRECTIONS });
};

const createPromptsSortControlDefinition = (state: SortState<PromptsSortColumn>): SortControlDefinition<PromptsSortColumn> => ({
    id: 'prompts-sort',
    className: 'page-header-filter-select prompts-sort',
    shellClassName: 'page-header-filter-select-shell',
    state,
    prefix: i18n.t('common.filters.sortBy'),
    ascendingLabel: i18n.t('common.sorting.ascending'),
    descendingLabel: i18n.t('common.sorting.descending'),
    inactiveColumn: 'none',
    options: [
        { column: 'none', label: i18n.t('common.sorting.none'), standaloneSelectionLabel: true },
        { column: 'date', label: i18n.t('prompts.sort.date') },
        { column: 'name', label: i18n.t('prompts.sort.name') },
        { column: 'color', label: i18n.t('prompts.sort.color') }
    ]
});

const hydratePromptsPageControls = (host: PromptsRuntimeContext): void => {
    const storage = requirePageControlsStorage(host.owners.storage);
    const saved = storage.getPageControlState('prompts');
    const sort = normalizePromptsSortState(saved);
    host.controls.setSortBy(sort.column);
    host.controls.setSortOrder(sort.direction);
    host.controls.setSearchQuery('');
    if (saved.sortBy !== sort.column || saved.sortOrder !== sort.direction) storage.setPageControlState('prompts', { sortBy: sort.column, sortOrder: sort.direction });
};

const persistPromptsSort = (host: PromptsRuntimeContext, state: SortState<PromptsSortColumn>): void => {
    requirePageControlsStorage(host.owners.storage).setPageControlState('prompts', { sortBy: state.column, sortOrder: state.direction });
};

const getColorSortRank = (colorToolkit: ColorToolkitInterface, color: string | null): number => {
    const normalized = colorToolkit.normalize(color);
    const key = normalized?.toLowerCase() ?? 'none';
    const index = colorToolkit.groups.findIndex((group) => group.key === key);
    return index < 0 ? colorToolkit.groups.length : index;
};

const getPromptsListSortValue = (item: ResourceItem, field: string, colorToolkit: ColorToolkitInterface): string | number => {
    if (field === 'name') return typeof item.name === 'string' ? item.name : '';
    if (field === 'color') return getColorSortRank(colorToolkit, typeof item['color'] === 'string' ? item['color'] : null);
    const value = item['modifiedAtMs'];
    if (typeof value !== 'number') {
        throw new TypeError('Prompts date sorting requires a normalized modifiedAtMs timestamp');
    }
    return value;
};

const syncPromptsSortControls = (host: PromptsRuntimeContext): void => {
    const state = normalizePromptsSortState({ sortBy: host.controls.getSortBy() ?? 'none', sortOrder: host.controls.getSortOrder() ?? 'asc' });
    const select = host.owners.pageDom.optionalHTMLElement('prompts-sort');
    if (select) {
        if (!(select instanceof HTMLSelectElement)) throw new TypeError('Prompts sort control must be an HTMLSelectElement');
        syncSortControl(select, createPromptsSortControlDefinition(state));
    }
    const table = host.owners.pageDom.optional('.prompts-list-table');
    if (table) syncSortableListIndicators({ services: host.owners.services, sortBy: state.column, sortOrder: state.direction }, table, 'Prompts');
};

const applyPromptsSortSelection = (host: PromptsRuntimeContext, requestedColumn: string): void => {
    const column = requireSortableColumn(PROMPTS_SORT_COLUMNS, requestedColumn, 'Prompts');
    applySortControlSelection({
        requestedColumn: column,
        host: {
            services: host.owners.services,
            get sortBy() {
                return host.controls.getSortBy();
            },
            set sortBy(value) {
                host.controls.setSortBy(value ?? 'none');
            },
            get sortOrder() {
                return host.controls.getSortOrder();
            },
            set sortOrder(value) {
                host.controls.setSortOrder(value);
            }
        },
        columns: PROMPTS_SORT_COLUMNS,
        defaultDirections: PROMPTS_SORT_DEFAULT_DIRECTIONS,
        inactiveColumn: 'none',
        reapplyCollection: (options) => host.operations.reapplyCollection(options),
        afterSort: (nextColumn, direction) => {
            persistPromptsSort(host, { column: nextColumn, direction });
            syncPromptsSortControls(host);
        }
    });
};

const sortPromptsListFromHeader = (host: PromptsRuntimeContext, actionElement: HTMLElement): void => {
    sortCollectionListFromHeader({
        actionElement,
        host: {
            services: host.owners.services,
            get sortBy() {
                return host.controls.getSortBy();
            },
            set sortBy(value) {
                host.controls.setSortBy(value ?? 'none');
            },
            get sortOrder() {
                return host.controls.getSortOrder();
            },
            set sortOrder(value) {
                host.controls.setSortOrder(value);
            }
        },
        columns: PROMPTS_LIST_SORT_COLUMNS,
        defaultDirections: PROMPTS_SORT_DEFAULT_DIRECTIONS,
        context: 'Prompts',
        reapplyCollection: (options) => host.operations.reapplyCollection(options),
        afterSort: (column, direction) => {
            persistPromptsSort(host, { column, direction });
            syncPromptsSortControls(host);
        }
    });
};

const applyPromptsListSortIndicators = (host: PromptsRuntimeContext, table: Element): void => {
    syncSortableListIndicators({ services: host.owners.services, sortBy: host.controls.getSortBy(), sortOrder: host.controls.getSortOrder() }, table, 'Prompts');
};

export { applyPromptsListSortIndicators, applyPromptsSortSelection, createPromptsSortControlDefinition, getPromptsListSortValue, hydratePromptsPageControls, normalizePromptsSortState, sortPromptsListFromHeader, syncPromptsSortControls };
export type { PromptsSortColumn };
