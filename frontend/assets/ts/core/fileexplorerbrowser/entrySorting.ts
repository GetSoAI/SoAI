/* SoAI - File explorer entry sorting [frontend/assets/ts/core/fileexplorerbrowser/entrySorting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileBrowserEntry } from '@core/fileexplorerbrowser/types.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';

type FileExplorerSortColumn = 'name' | 'type' | 'size' | 'modified';

const FILE_EXPLORER_SORT_COLUMNS: readonly FileExplorerSortColumn[] = ['name', 'type', 'size', 'modified'];

const FILE_EXPLORER_SORT_COLUMN_DEFAULT_DIRECTIONS: Readonly<Record<FileExplorerSortColumn, SortDirection>> = {
    name: 'asc',
    type: 'asc',
    size: 'desc',
    modified: 'desc'
};

const compareNamesAscending = (entryA: FileBrowserEntry, entryB: FileBrowserEntry, locale: string): number => entryA.name.localeCompare(entryB.name, locale, { sensitivity: 'base' });

const compareTypeGroupAscending = (entryA: FileBrowserEntry, entryB: FileBrowserEntry): number => {
    const rankComparison = entryA.typeRank - entryB.typeRank;
    if (rankComparison !== 0) {
        return rankComparison;
    }
    return entryA.typeId.localeCompare(entryB.typeId, 'en');
};

const sortFileExplorerEntries = (entries: readonly FileBrowserEntry[], column: FileExplorerSortColumn, direction: SortDirection): readonly FileBrowserEntry[] => {
    const multiplier = direction === 'asc' ? 1 : -1;
    const locale = getCurrentLocale();
    return [...entries].sort((entryA, entryB) => {
        if (column !== 'type' && entryA.isDirectory !== entryB.isDirectory) {
            return entryA.isDirectory ? -1 : 1;
        }
        switch (column) {
            case 'name':
                return multiplier * compareNamesAscending(entryA, entryB, locale);
            case 'type': {
                const typeComparison = compareTypeGroupAscending(entryA, entryB);
                if (typeComparison !== 0) {
                    return multiplier * typeComparison;
                }
                return compareNamesAscending(entryA, entryB, locale);
            }
            case 'size':
                return multiplier * (entryA.size - entryB.size);
            case 'modified':
                return multiplier * (entryA.modifiedAtTimestamp - entryB.modifiedAtTimestamp);
        }
    });
};

export { FILE_EXPLORER_SORT_COLUMN_DEFAULT_DIRECTIONS, FILE_EXPLORER_SORT_COLUMNS, sortFileExplorerEntries };
export type { FileExplorerSortColumn };
