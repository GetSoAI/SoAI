/* SoAI - Shared UI primitives sortable list [frontend/assets/ts/core/uiprimitives/sortableList.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireClosestElement, requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { requireSortableColumn, requireSortableHeaders, resolveNextSortState, updateSortableTableIndicators, type SortDirection, type SortState } from '@core/ui/tables/sortableTable.ts';
import { renderRepeatableDropdownSelectControl, syncRepeatableDropdownSelect } from '@core/ui/dropdown/selectControl.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { UiAttributeValue } from '@core/security/uiHtml.ts';

interface SortableListHost extends PageServicesOwnerHost {
    sortBy: string | null;
    sortOrder: SortDirection | null;
}

interface SortableListOptions<TColumn extends string> {
    actionElement: HTMLElement;
    host: SortableListHost;
    columns: readonly TColumn[];
    defaultDirections: Record<TColumn, SortDirection>;
    context: string;
    reapplyCollection: (options: { shouldRender: boolean; updateStats: boolean; updateFilters: boolean; resetScroll: boolean }) => void;
    afterSort?: ((column: TColumn, direction: SortDirection) => void) | undefined;
}

interface ApplySortControlSelectionOptions<TColumn extends string> {
    requestedColumn: TColumn;
    host: SortableListHost;
    columns: readonly TColumn[];
    defaultDirections: Record<TColumn, SortDirection>;
    inactiveColumn?: TColumn;
    reapplyCollection: (options: { shouldRender: boolean; updateStats: boolean; updateFilters: boolean; resetScroll: boolean }) => void;
    afterSort?: ((column: TColumn, direction: SortDirection) => void) | undefined;
}

interface SortControlSelectionLabels {
    prefix: string;
    column: string;
    ascending: string;
    descending: string;
    standalone?: boolean;
    inactive?: boolean;
}

interface SortControlSelectionLabel {
    visual: string;
    accessible: string;
}

interface SortControlOption<TColumn extends string> {
    column: TColumn;
    label: string;
    standaloneSelectionLabel?: boolean;
}

interface SortControlDefinition<TColumn extends string> {
    id: string;
    className: string;
    shellClassName?: string;
    state: SortState<TColumn>;
    prefix: string;
    ascendingLabel: string;
    descendingLabel: string;
    inactiveColumn?: TColumn;
    options: readonly SortControlOption<TColumn>[];
    attributes?: Readonly<Record<string, UiAttributeValue>>;
}

const SORT_DIRECTION_MARKERS: Record<SortDirection, string> = { asc: '▴', desc: '▾' };

const resolveCurrentSortColumn = <TColumn extends string>(columns: readonly TColumn[], value: string | null): TColumn | null => {
    const match = columns.find((column) => column === value);
    return match ?? null;
};

const resolveSortControlState = <TColumn extends string>(current: SortState<TColumn>, requestedColumn: TColumn, defaultDirections: Record<TColumn, SortDirection>, inactiveColumn?: TColumn): SortState<TColumn> => {
    if (requestedColumn === inactiveColumn) {
        return { column: requestedColumn, direction: defaultDirections[requestedColumn] };
    }
    return resolveNextSortState(current, requestedColumn, defaultDirections[requestedColumn]);
};

const formatSortControlSelectionLabel = (state: { direction: SortDirection }, labels: SortControlSelectionLabels): SortControlSelectionLabel => {
    const baseLabel = labels.standalone === true ? labels.column : `${labels.prefix} ${labels.column}`;
    if (labels.inactive === true) {
        return { visual: baseLabel, accessible: baseLabel };
    }
    const directionLabel = state.direction === 'asc' ? labels.ascending : labels.descending;
    return {
        visual: `${baseLabel} ${SORT_DIRECTION_MARKERS[state.direction]}`,
        accessible: `${baseLabel}, ${directionLabel}`
    };
};

const resolveSortControlSelectionLabel = <TColumn extends string>(definition: SortControlDefinition<TColumn>): SortControlSelectionLabel => {
    const option = definition.options.find((candidate) => candidate.column === definition.state.column);
    if (!option) throw new Error(`Sort control ${definition.id} is missing active column ${definition.state.column}`);
    return formatSortControlSelectionLabel(definition.state, {
        prefix: definition.prefix,
        column: option.label,
        ascending: definition.ascendingLabel,
        descending: definition.descendingLabel,
        standalone: option.standaloneSelectionLabel === true,
        inactive: option.column === definition.inactiveColumn
    });
};

const renderSortControl = <TColumn extends string>(definition: SortControlDefinition<TColumn>): TrustedHtml => {
    const selectionLabel = resolveSortControlSelectionLabel(definition);
    return renderRepeatableDropdownSelectControl({
        id: definition.id,
        className: definition.className,
        ...(definition.shellClassName ? { shellClassName: definition.shellClassName } : {}),
        selectionLabel: selectionLabel.visual,
        accessibleLabel: selectionLabel.accessible,
        options: definition.options.map((option) => ({ value: option.column, label: option.label })),
        ...(definition.attributes ? { attributes: definition.attributes } : {})
    });
};

const syncSortControl = <TColumn extends string>(select: HTMLSelectElement, definition: SortControlDefinition<TColumn>): void => {
    const selectionLabel = resolveSortControlSelectionLabel(definition);
    syncRepeatableDropdownSelect(select, selectionLabel.visual, selectionLabel.accessible);
};

const syncSortableListIndicators = (host: SortableListHost, table: Element, context: string, fallbackColumn?: string): void => {
    const headers = requireSortableHeaders(table, context);
    const requestedColumn = host.sortBy && host.sortBy !== 'none' ? host.sortBy : fallbackColumn;
    const activeColumn = headers.some((header) => header.sortKey === requestedColumn) ? requestedColumn : fallbackColumn;
    const activeDirection = host.sortOrder;
    if (!activeColumn || !activeDirection) {
        updateSortableTableIndicators({ headers, activeColumn: null, activeDirection: null, host: { getIconSync: (iconName, iconOptions) => host.services.getIconSync(iconName, iconOptions) } });
        return;
    }
    updateSortableTableIndicators({
        headers,
        activeColumn,
        activeDirection,
        host: { getIconSync: (iconName, iconOptions) => host.services.getIconSync(iconName, iconOptions) }
    });
};

const applySortControlSelection = <TColumn extends string>(options: ApplySortControlSelectionOptions<TColumn>): SortState<TColumn> => {
    const currentColumn = resolveCurrentSortColumn(options.columns, options.host.sortBy);
    const currentDirection = options.host.sortOrder ?? options.defaultDirections[options.requestedColumn];
    const next = currentColumn ? resolveSortControlState({ column: currentColumn, direction: currentDirection }, options.requestedColumn, options.defaultDirections, options.inactiveColumn) : { column: options.requestedColumn, direction: options.defaultDirections[options.requestedColumn] };
    if (currentColumn === options.inactiveColumn && next.column === currentColumn && next.direction === currentDirection) return next;
    options.host.sortBy = next.column;
    options.host.sortOrder = next.direction;
    options.afterSort?.(next.column, next.direction);
    options.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: false, resetScroll: true });
    return next;
};

const sortCollectionListFromHeader = <TColumn extends string>(options: SortableListOptions<TColumn>): void => {
    const sortKey = requireTrimmedDataAttribute(options.actionElement, 'sort', `${options.context} sort action`);
    const column = requireSortableColumn(options.columns, sortKey, options.context);
    const table = requireClosestElement(options.actionElement, 'table', `${options.context} sort action`);
    applySortControlSelection({
        requestedColumn: column,
        host: options.host,
        columns: options.columns,
        defaultDirections: options.defaultDirections,
        reapplyCollection: options.reapplyCollection,
        afterSort: (nextColumn, nextDirection) => {
            syncSortableListIndicators(options.host, table, options.context);
            options.afterSort?.(nextColumn, nextDirection);
        }
    });
};

export { applySortControlSelection, formatSortControlSelectionLabel, renderSortControl, resolveSortControlState, sortCollectionListFromHeader, syncSortControl, syncSortableListIndicators };
export type { ApplySortControlSelectionOptions, SortControlDefinition, SortControlOption, SortControlSelectionLabel, SortControlSelectionLabels, SortableListHost, SortableListOptions };
