/* SoAI - Assistant Markdown table sorting interaction [frontend/assets/ts/features/chat/message/markdownTableSorting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { requireNonNegativeIntegerAttribute } from '@core/dom/attributes.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { normalizeSortDirection, requireSortableHeaders, resolveNextSortState, updateSortableTableIndicators, type SortableHeaderRef, type SortDirection, type SortState } from '@core/ui/tables/sortableTable.ts';

const MARKDOWN_TABLE_HEADER_SELECTOR = 'th.markdown-table-sortable-header';
const MARKDOWN_TABLE_SELECTOR = 'table.markdown-table.markdown-table-sortable';
const MARKDOWN_TABLE_INDICATOR_OVERLAY_CLASS = 'is-space-overlay';
const MARKDOWN_TABLE_INDICATOR_SIZE_PX = 14;
const MARKDOWN_TABLE_INDICATOR_STROKE_WIDTH = 2.5;

type SortableMarkdownRow = {
    row: HTMLTableRowElement;
    sourceIndex: number;
    values: string[];
};

type SortableMarkdownTableContext = {
    body: HTMLTableSectionElement;
    headers: readonly SortableHeaderRef[];
    rows: SortableMarkdownRow[];
};

const requireSortableMarkdownTable = (header: HTMLElement): HTMLTableElement => {
    const table = header.closest(MARKDOWN_TABLE_SELECTOR);
    if (!(table instanceof HTMLTableElement)) {
        throw new Error('Assistant Markdown table sort action requires a sortable Markdown table');
    }
    return table;
};

const requireSortableMarkdownTableContext = (table: HTMLTableElement): SortableMarkdownTableContext => {
    const headers = requireSortableHeaders(table, 'Assistant Markdown table', MARKDOWN_TABLE_HEADER_SELECTOR);
    const tableHead = table.tHead;
    if (!(tableHead instanceof HTMLTableSectionElement) || tableHead.rows.length !== 1) {
        throw new Error('Assistant Markdown table sorting requires exactly one header row');
    }
    const headerRow = tableHead.rows.item(0);
    if (!(headerRow instanceof HTMLTableRowElement) || headerRow.cells.length !== headers.length) {
        throw new Error('Assistant Markdown table sorting requires canonical header cells');
    }
    for (let columnIndex = 0; columnIndex < headers.length; columnIndex += 1) {
        const header = headers[columnIndex];
        if (!header || header.header !== headerRow.cells.item(columnIndex) || header.sortKey !== String(columnIndex)) {
            throw new Error('Assistant Markdown table sorting requires sequential canonical column headers');
        }
    }
    if (table.tBodies.length !== 1) {
        throw new Error('Assistant Markdown table sorting requires exactly one table body');
    }
    const body = table.tBodies.item(0);
    if (!(body instanceof HTMLTableSectionElement)) {
        throw new Error('Assistant Markdown table sorting requires a table body');
    }
    const sourceIndexes = new Set<number>();
    const rows: SortableMarkdownRow[] = [];
    for (const row of Array.from(body.rows)) {
        if (row.cells.length !== headers.length) {
            throw new Error('Assistant Markdown table sorting requires rows matching the header column count');
        }
        const sourceIndex = requireNonNegativeIntegerAttribute(row, 'data-markdown-table-source-index', 'Assistant Markdown table row');
        if (sourceIndexes.has(sourceIndex)) {
            throw new Error('Assistant Markdown table sorting requires unique source row indexes');
        }
        sourceIndexes.add(sourceIndex);
        rows.push({ row, sourceIndex, values: Array.from(row.cells).map((cell) => (cell.textContent ?? '').trim()) });
    }
    const orderedSourceIndexes = [...sourceIndexes].sort((left, right) => left - right);
    if (orderedSourceIndexes.some((sourceIndex, position) => sourceIndex !== position)) {
        throw new Error('Assistant Markdown table sorting requires contiguous source row indexes');
    }
    return { body, headers, rows };
};

const resolveCurrentSortState = (table: HTMLTableElement): SortState<string> => {
    const column = table.dataset['sortColumn'];
    const direction = table.dataset['sortDirection'];
    if (column === undefined && direction === undefined) {
        return { column: '', direction: 'desc' };
    }
    if (!column || !direction) {
        throw new Error('Assistant Markdown table has incomplete sort state');
    }
    return { column, direction: normalizeSortDirection(direction) };
};

const sortRows = (rows: readonly SortableMarkdownRow[], columnIndex: number, direction: SortDirection): HTMLTableRowElement[] => {
    const multiplier = direction === 'asc' ? 1 : -1;
    const collator = new Intl.Collator(getCurrentLocale(), { numeric: true, sensitivity: 'base' });
    return [...rows]
        .sort((left, right) => {
            const leftValue = left.values[columnIndex] ?? '';
            const rightValue = right.values[columnIndex] ?? '';
            const comparison = collator.compare(leftValue, rightValue);
            return comparison === 0 ? left.sourceIndex - right.sourceIndex : multiplier * comparison;
        })
        .map((entry) => entry.row);
};

const canOverlayIndicatorWithinExistingSpace = (header: HTMLElement, indicator: HTMLElement): boolean => {
    if (indicator.childNodes.length > 0) {
        return indicator.classList.contains(MARKDOWN_TABLE_INDICATOR_OVERLAY_CLASS);
    }
    const headerRect = measureLayoutBox(header);
    if (headerRect.width <= 0) {
        return false;
    }
    const headerStyles = getComputedStyleStrict(header);
    const rootStyles = getComputedStyleStrict(header.ownerDocument.documentElement);
    const paddingRight = Number.parseFloat(headerStyles.paddingRight);
    const rootFontSize = Number.parseFloat(rootStyles.fontSize);
    if (!isFiniteNumber(paddingRight) || !isFiniteNumber(rootFontSize)) {
        throw new Error('Assistant Markdown table sorting requires measurable header spacing');
    }
    const labelRange = header.ownerDocument.createRange();
    labelRange.setStart(header, 0);
    labelRange.setEndBefore(indicator);
    const labelRect = measureLayoutBox(labelRange);
    const availableSpace = headerRect.right - paddingRight - labelRect.right;
    return availableSpace >= MARKDOWN_TABLE_INDICATOR_SIZE_PX + rootFontSize * 0.25;
};

const applyMarkdownTableSort = (header: HTMLElement): void => {
    const table = requireSortableMarkdownTable(header);
    const context = requireSortableMarkdownTableContext(table);
    const requestedColumn = header.dataset['sort'];
    const activeHeader = context.headers.find((entry) => entry.header === header);
    if (!requestedColumn || activeHeader === undefined) {
        throw new Error('Assistant Markdown table sort action requires a canonical column header');
    }
    const columnIndex = requireNonNegativeIntegerAttribute(header, 'data-sort', 'Assistant Markdown table header');
    if (columnIndex >= context.headers.length) {
        throw new Error('Assistant Markdown table sort column exceeds the header count');
    }
    const nextState = resolveNextSortState(resolveCurrentSortState(table), requestedColumn, 'asc');
    const orderedRows = sortRows(context.rows, columnIndex, nextState.direction);
    const iconName = nextState.direction === 'asc' ? 'chevron-up' : 'chevron-down';
    const overlayIndicator = canOverlayIndicatorWithinExistingSpace(header, activeHeader.indicator);
    const iconHtml = getIconSync(iconName, { size: MARKDOWN_TABLE_INDICATOR_SIZE_PX, strokeWidth: MARKDOWN_TABLE_INDICATOR_STROKE_WIDTH });
    const indicatorHost = {
        getIconSync: (requestedIconName: Parameters<typeof getIconSync>[0], requestedOptions?: Parameters<typeof getIconSync>[1]): typeof iconHtml => {
            if (requestedIconName !== iconName || requestedOptions === undefined || requestedOptions.size !== MARKDOWN_TABLE_INDICATOR_SIZE_PX || requestedOptions.strokeWidth !== MARKDOWN_TABLE_INDICATOR_STROKE_WIDTH) {
                throw new Error('Assistant Markdown table indicator requested an unexpected icon');
            }
            return iconHtml;
        }
    };

    context.body.replaceChildren(...orderedRows);
    table.dataset['sortColumn'] = nextState.column;
    table.dataset['sortDirection'] = nextState.direction;
    updateSortableTableIndicators({ headers: context.headers, activeColumn: nextState.column, activeDirection: nextState.direction, host: indicatorHost });
    for (const sortableHeader of context.headers) {
        sortableHeader.indicator.classList.toggle(MARKDOWN_TABLE_INDICATOR_OVERLAY_CLASS, sortableHeader.header === header && overlayIndicator);
    }
};

const resolveMarkdownTableSortHeader = (target: EventTarget | null): HTMLElement | null => {
    if (!(target instanceof Element)) {
        return null;
    }
    const header = target.closest(MARKDOWN_TABLE_HEADER_SELECTOR);
    return header instanceof HTMLElement ? header : null;
};

const isMarkdownTableHeaderLinkTarget = (target: EventTarget | null, header: HTMLElement): boolean => {
    if (!(target instanceof Element)) {
        return false;
    }
    const link = target.closest('a');
    return link instanceof HTMLAnchorElement && header.contains(link);
};

const restoreMarkdownTableRows = (table: HTMLTableElement, column: string, direction: SortDirection): void => {
    const context = requireSortableMarkdownTableContext(table);
    const header = context.headers.find((entry) => entry.sortKey === column)?.header ?? null;
    if (!(header instanceof HTMLElement)) {
        throw new Error('Assistant Markdown table preserved sort column is missing');
    }
    const columnIndex = requireNonNegativeIntegerAttribute(header, 'data-sort', 'Assistant Markdown table header');
    context.body.replaceChildren(...sortRows(context.rows, columnIndex, direction));
    table.dataset['sortColumn'] = column;
    table.dataset['sortDirection'] = direction;
};

const restoreMarkdownTableSourceOrder = (table: HTMLTableElement): void => {
    const context = requireSortableMarkdownTableContext(table);
    const orderedRows = [...context.rows].sort((left, right) => left.sourceIndex - right.sourceIndex).map((entry) => entry.row);
    context.body.replaceChildren(...orderedRows);
};

const resolveMarkdownTableSourceSignature = (table: HTMLTableElement): string => {
    const context = requireSortableMarkdownTableContext(table);
    const headers = context.headers.map((entry) => (entry.header.textContent ?? '').trim());
    const rows = [...context.rows].sort((left, right) => left.sourceIndex - right.sourceIndex).map((entry) => entry.values);
    return JSON.stringify({ headers, rows });
};

export { applyMarkdownTableSort, isMarkdownTableHeaderLinkTarget, MARKDOWN_TABLE_HEADER_SELECTOR, MARKDOWN_TABLE_INDICATOR_OVERLAY_CLASS, MARKDOWN_TABLE_SELECTOR, resolveMarkdownTableSortHeader, resolveMarkdownTableSourceSignature, restoreMarkdownTableRows, restoreMarkdownTableSourceOrder };
