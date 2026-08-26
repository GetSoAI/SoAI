/* SoAI - File explorer page control layer controls controller [frontend/assets/ts/pages/fileexplorer/controllers/page/fileExplorerPageControlsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FILE_EXPLORER_SORT_COLUMN_DEFAULT_DIRECTIONS, FILE_EXPLORER_SORT_COLUMNS, type FileExplorerSortColumn } from '@core/fileexplorerbrowser/entrySorting.ts';
import { requirePageControlsStorage, type PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import { i18n } from '@core/i18n/index.ts';
import { normalizeStoredSortState, type SortDirection, type SortState } from '@core/ui/tables/sortableTable.ts';
import type { SortControlDefinition } from '@core/uiprimitives/sortableList.ts';

interface FileExplorerSortState {
    column: FileExplorerSortColumn;
    direction: SortDirection;
}

const readFileExplorerSortState = (storage: PageControlsStorageInput): FileExplorerSortState => {
    const state = requirePageControlsStorage(storage).getPageControlState('fileExplorer');
    return normalizeStoredSortState({ state: { column: state.sortBy, direction: state.sortOrder }, columns: FILE_EXPLORER_SORT_COLUMNS, fallback: { column: 'name', direction: 'asc' }, defaultDirections: FILE_EXPLORER_SORT_COLUMN_DEFAULT_DIRECTIONS });
};

const hydrateFileExplorerSortState = (storage: PageControlsStorageInput): FileExplorerSortState => {
    const controls = requirePageControlsStorage(storage);
    const saved = controls.getPageControlState('fileExplorer');
    const state = readFileExplorerSortState(storage);
    if (saved.sortBy !== state.column || saved.sortOrder !== state.direction) controls.setPageControlState('fileExplorer', { sortBy: state.column, sortOrder: state.direction });
    return state;
};

const createFileExplorerSortControlDefinition = (state: SortState<FileExplorerSortColumn>, hidden = false): SortControlDefinition<FileExplorerSortColumn> => ({
    id: 'file-explorer-icon-sort',
    className: 'page-header-filter-select file-explorer-icon-sort',
    shellClassName: hidden ? 'file-explorer-sort-shell u-hidden' : 'file-explorer-sort-shell',
    state,
    prefix: i18n.t('common.filters.sortBy'),
    ascendingLabel: i18n.t('common.sorting.ascending'),
    descendingLabel: i18n.t('common.sorting.descending'),
    attributes: { 'aria-label': i18n.t('fileExplorer.actions.sortLabel'), hidden },
    options: [
        { column: 'name', label: i18n.t('fileExplorer.table.name') },
        { column: 'type', label: i18n.t('fileExplorer.table.type') },
        { column: 'size', label: i18n.t('fileExplorer.table.size') },
        { column: 'modified', label: i18n.t('fileExplorer.table.modified') }
    ]
});

const persistFileExplorerSortState = (storage: PageControlsStorageInput, state: FileExplorerSortState): void => {
    requirePageControlsStorage(storage).setPageControlState('fileExplorer', {
        sortBy: state.column,
        sortOrder: state.direction
    });
};

export { createFileExplorerSortControlDefinition, hydrateFileExplorerSortState, persistFileExplorerSortState, readFileExplorerSortState };
export type { FileExplorerSortState };
