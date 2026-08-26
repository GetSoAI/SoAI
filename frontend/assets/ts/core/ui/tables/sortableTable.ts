/* SoAI - Shared UI sortable table [frontend/assets/ts/core/ui/tables/sortableTable.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

type SortDirection = 'asc' | 'desc';

interface SortState<TColumn extends string = string> {
    column: TColumn;
    direction: SortDirection;
}

interface SortableHeaderRef {
    header: HTMLElement;
    indicator: HTMLElement;
    sortKey: string;
}

interface SortableIndicatorHost {
    getIconSync: (name: IconName, options?: IconOptions) => TrustedHtml;
}

interface UpdateSortableIndicatorsArguments {
    headers: readonly SortableHeaderRef[];
    activeColumn: string | null;
    activeDirection: string | null;
    host: SortableIndicatorHost;
}

interface NormalizeStoredSortStateArguments<TColumn extends string> {
    state: { column: string; direction: string };
    columns: readonly TColumn[];
    fallback: SortState<TColumn>;
    defaultDirections: Readonly<Record<TColumn, SortDirection>>;
}

const normalizeSortDirection = (direction: string): SortDirection => {
    if (direction === 'asc' || direction === 'desc') {
        return direction;
    }
    throw new Error(`Invalid sortable table direction: ${direction}`);
};

const resolveSortableAriaSortValue = (direction: SortDirection | 'none'): 'ascending' | 'descending' | 'none' => {
    if (direction === 'none') {
        return 'none';
    }
    return direction === 'asc' ? 'ascending' : 'descending';
};

const resolveNextSortState = <TColumn extends string>(current: SortState<TColumn>, requestedColumn: TColumn, defaultDirection: SortDirection): SortState<TColumn> => {
    if (current.column === requestedColumn) {
        return { column: requestedColumn, direction: current.direction === 'asc' ? 'desc' : 'asc' };
    }
    return { column: requestedColumn, direction: defaultDirection };
};

const normalizeStoredSortState = <TColumn extends string>(inputArguments: NormalizeStoredSortStateArguments<TColumn>): SortState<TColumn> => {
    const column = inputArguments.columns.find((allowedColumn) => allowedColumn === inputArguments.state.column);
    if (!column) return inputArguments.fallback;
    const direction = inputArguments.state.direction === 'asc' || inputArguments.state.direction === 'desc' ? inputArguments.state.direction : inputArguments.defaultDirections[column];
    return { column, direction };
};

const requireSortableColumn = <TColumn extends string>(columns: readonly TColumn[], column: string, contextLabel: string): TColumn => {
    for (const allowedColumn of columns) {
        if (allowedColumn === column) {
            return allowedColumn;
        }
    }
    throw new Error(`Unsupported ${contextLabel} sort column: ${column}`);
};

const requireSortableHeaders = (table: Element, contextLabel: string, headerSelector: string = 'th.sortable'): readonly SortableHeaderRef[] => {
    const headers = dom.resolveAll(headerSelector, table);
    if (headers.length <= 0) {
        throw new Error(`${contextLabel} table is missing required sortable headers`);
    }
    const sortKeys = new Set<string>();
    return headers.map((header) => {
        if (!(header instanceof HTMLElement)) {
            throw new Error(`${contextLabel} sortable header must be an HTMLElement`);
        }
        const sortKey = header.dataset['sort'];
        if (!sortKey) {
            throw new Error(`${contextLabel} sortable header is missing required data-sort attribute`);
        }
        if (sortKeys.has(sortKey)) {
            throw new Error(`${contextLabel} sortable headers include duplicate data-sort attribute: ${sortKey}`);
        }
        sortKeys.add(sortKey);
        const indicator = dom.resolve('.sort-indicator', header);
        if (!(indicator instanceof HTMLElement)) {
            throw new Error(`${contextLabel} sortable header is missing required .sort-indicator element`);
        }
        return { header, indicator, sortKey };
    });
};

const updateSortableTableIndicators = (inputArguments: UpdateSortableIndicatorsArguments): void => {
    if (inputArguments.activeColumn === null || inputArguments.activeDirection === null) {
        for (const header of inputArguments.headers) {
            header.header.classList.remove('is-active');
            header.indicator.replaceChildren();
            header.header.setAttribute('aria-sort', 'none');
        }
        return;
    }
    const direction = normalizeSortDirection(inputArguments.activeDirection);
    let matchedActiveColumn = false;
    for (const header of inputArguments.headers) {
        if (header.sortKey === inputArguments.activeColumn) {
            matchedActiveColumn = true;
            break;
        }
    }
    if (!matchedActiveColumn) {
        throw new Error(`Sortable table is missing active sort column header: ${inputArguments.activeColumn}`);
    }
    for (const header of inputArguments.headers) {
        const isActive = header.sortKey === inputArguments.activeColumn;
        header.header.classList.toggle('is-active', isActive);
        if (isActive) {
            const iconName: IconName = direction === 'asc' ? 'chevron-up' : 'chevron-down';
            dom.setHTML(header.indicator, inputArguments.host.getIconSync(iconName, { size: 14, strokeWidth: 2.5 }), { escape: false });
            header.header.setAttribute('aria-sort', resolveSortableAriaSortValue(direction));
        } else {
            header.indicator.replaceChildren();
            header.header.setAttribute('aria-sort', 'none');
        }
    }
};

export { normalizeSortDirection, normalizeStoredSortState, requireSortableColumn, requireSortableHeaders, resolveNextSortState, resolveSortableAriaSortValue, updateSortableTableIndicators };
export type { NormalizeStoredSortStateArguments, SortableHeaderRef, SortDirection, SortState };
