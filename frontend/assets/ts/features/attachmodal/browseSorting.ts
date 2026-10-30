/* SoAI - Attachment browser sorting policy [frontend/assets/ts/features/attachmodal/browseSorting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCurrentLocale } from '@core/languageservice/service.ts';
import { getCollator } from '@core/localization/intlCache.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';
import type { AttachBrowseResult, AttachBrowseSortColumn, AttachBrowseSortState } from '@features/attachmodal/browseRecords.ts';

const ATTACH_BROWSE_SORT_COLUMNS: readonly AttachBrowseSortColumn[] = ['name', 'type', 'size', 'modified'];
const ATTACH_BROWSE_SORT_DIRECTIONS: Readonly<Record<AttachBrowseSortColumn, SortDirection>> = { name: 'asc', type: 'asc', size: 'desc', modified: 'desc' };

const compareText = (left: string, right: string, collator: Intl.Collator): number => collator.compare(left, right);

const sortBrowseResults = <TResult extends AttachBrowseResult>(results: readonly TResult[], sortState: AttachBrowseSortState): TResult[] => {
    const multiplier = sortState.direction === 'asc' ? 1 : -1;
    const collator = getCollator(getCurrentLocale(), { sensitivity: 'base' });
    return [...results].sort((left, right) => {
        switch (sortState.column) {
            case 'name':
                return multiplier * compareText(left.title, right.title, collator);
            case 'type': {
                const typeComparison = compareText(left.typeLabel, right.typeLabel, collator);
                if (typeComparison !== 0) {
                    return multiplier * typeComparison;
                }
                return compareText(left.title, right.title, collator);
            }
            case 'size':
                return multiplier * (left.sortSize - right.sortSize);
            case 'modified':
                return multiplier * (left.sortModified - right.sortModified);
        }
    });
};

export { ATTACH_BROWSE_SORT_COLUMNS, ATTACH_BROWSE_SORT_DIRECTIONS, sortBrowseResults };
