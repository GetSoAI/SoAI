/* SoAI - Assistant Markdown table sort state preservation [frontend/assets/ts/features/chat/message/assistantMarkdownTableSortState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { normalizeSortDirection, requireSortableHeaders, resolveSortableAriaSortValue, type SortDirection } from '@core/ui/tables/sortableTable.ts';
import { MARKDOWN_TABLE_HEADER_SELECTOR, MARKDOWN_TABLE_INDICATOR_OVERLAY_CLASS, MARKDOWN_TABLE_SELECTOR, resolveMarkdownTableSourceSignature, restoreMarkdownTableRows, restoreMarkdownTableSourceOrder } from '@features/chat/message/markdownTableSorting.ts';
import { collectMatchingElements } from '@features/chat/stream/streamDomQueries.ts';

type MarkdownTableSortStateEntry = {
    tableKey: string;
    occurrence: number;
    matchingTableCount: number;
    sourceSignature: string;
    column: string;
    direction: SortDirection;
    indicatorOverlay: boolean;
    indicatorNodes: ChildNode[];
};

type MarkdownTableSortState = MarkdownTableSortStateEntry[];
type KeyedMarkdownTable = { table: HTMLTableElement; tableKey: string };
type MarkdownTableSortRestore = { table: HTMLTableElement; preserved: MarkdownTableSortStateEntry };

const cloneChildNode = (node: ChildNode): ChildNode => {
    const documentRef = node.ownerDocument;
    if (documentRef === null) {
        throw new Error('Assistant Markdown table indicator requires an owner document');
    }
    return documentRef.importNode(node, true);
};

const collectKeyedMarkdownTables = (root: Element): KeyedMarkdownTable[] => {
    return collectMatchingElements(root, MARKDOWN_TABLE_SELECTOR).map((element) => {
        if (!(element instanceof HTMLTableElement)) {
            throw new Error('Assistant Markdown table state requires an HTML table');
        }
        return {
            table: element,
            tableKey: requireTrimmedDataAttribute(element, 'markdownTableKey', 'Assistant Markdown table')
        };
    });
};

const countMarkdownTablesByKey = (tables: readonly KeyedMarkdownTable[]): Map<string, number> => {
    const countByKey = new Map<string, number>();
    for (const { tableKey } of tables) {
        countByKey.set(tableKey, (countByKey.get(tableKey) ?? 0) + 1);
    }
    return countByKey;
};

const requireMarkdownTableCount = (countByKey: ReadonlyMap<string, number>, tableKey: string): number => {
    const count = countByKey.get(tableKey);
    if (count === undefined) {
        throw new Error('Assistant Markdown table state requires a canonical table count');
    }
    return count;
};

const collectMarkdownTableSortState = (root: Element): MarkdownTableSortState => {
    const tables = collectKeyedMarkdownTables(root);
    const countByKey = countMarkdownTablesByKey(tables);
    const occurrenceByKey = new Map<string, number>();
    const state: MarkdownTableSortState = [];
    for (const { table, tableKey } of tables) {
        const occurrence = occurrenceByKey.get(tableKey) ?? 0;
        occurrenceByKey.set(tableKey, occurrence + 1);
        const column = table.dataset['sortColumn'];
        const rawDirection = table.dataset['sortDirection'];
        if (column === undefined && rawDirection === undefined) {
            continue;
        }
        if (!column || !rawDirection) {
            throw new Error('Assistant Markdown table has incomplete preserved sort state');
        }
        const direction = normalizeSortDirection(rawDirection);
        const headers = requireSortableHeaders(table, 'Assistant Markdown table', MARKDOWN_TABLE_HEADER_SELECTOR);
        const activeHeader = headers.find((entry) => entry.sortKey === column) ?? null;
        if (activeHeader === null || !activeHeader.header.classList.contains('is-active')) {
            throw new Error('Assistant Markdown table preserved sort state requires an active header');
        }
        if (activeHeader.header.getAttribute('aria-sort') !== resolveSortableAriaSortValue(direction) || activeHeader.indicator.childNodes.length === 0) {
            throw new Error('Assistant Markdown table preserved sort state requires a complete active indicator');
        }
        state.push({
            tableKey,
            occurrence,
            matchingTableCount: requireMarkdownTableCount(countByKey, tableKey),
            sourceSignature: resolveMarkdownTableSourceSignature(table),
            column,
            direction,
            indicatorOverlay: activeHeader.indicator.classList.contains(MARKDOWN_TABLE_INDICATOR_OVERLAY_CLASS),
            indicatorNodes: Array.from(activeHeader.indicator.childNodes).map(cloneChildNode)
        });
    }
    return state;
};

const restoreMarkdownTableSortState = (root: Element, state: MarkdownTableSortState): void => {
    if (state.length === 0) {
        return;
    }
    const preservedByIdentity = new Map(state.map((entry) => [`${entry.tableKey}:${String(entry.occurrence)}`, entry]));
    const tables = collectKeyedMarkdownTables(root);
    const countByKey = countMarkdownTablesByKey(tables);
    const occurrenceByKey = new Map<string, number>();
    const restorePlans: MarkdownTableSortRestore[] = [];
    for (const { table, tableKey } of tables) {
        const occurrence = occurrenceByKey.get(tableKey) ?? 0;
        occurrenceByKey.set(tableKey, occurrence + 1);
        const preserved = preservedByIdentity.get(`${tableKey}:${String(occurrence)}`) ?? null;
        if (preserved === null || preserved.matchingTableCount !== requireMarkdownTableCount(countByKey, tableKey) || preserved.sourceSignature !== resolveMarkdownTableSourceSignature(table)) {
            continue;
        }
        restorePlans.push({ table, preserved });
    }
    for (const { table, preserved } of restorePlans) {
        restoreMarkdownTableRows(table, preserved.column, preserved.direction);
        const headers = requireSortableHeaders(table, 'Assistant Markdown table', MARKDOWN_TABLE_HEADER_SELECTOR);
        for (const header of headers) {
            const active = header.sortKey === preserved.column;
            header.header.classList.toggle('is-active', active);
            header.header.setAttribute('aria-sort', active ? resolveSortableAriaSortValue(preserved.direction) : 'none');
            header.indicator.replaceChildren(...(active ? preserved.indicatorNodes.map(cloneChildNode) : []));
            header.indicator.classList.toggle(MARKDOWN_TABLE_INDICATOR_OVERLAY_CLASS, active && preserved.indicatorOverlay);
        }
    }
};

const hasMarkdownTableSortState = (root: Element): boolean => {
    return collectMatchingElements(root, `${MARKDOWN_TABLE_SELECTOR}[data-sort-column], ${MARKDOWN_TABLE_SELECTOR}[data-sort-direction]`).length > 0;
};

const normalizeSerializedMarkdownTableSortState = (root: Element): boolean => {
    let changed = false;
    for (const element of collectMatchingElements(root, MARKDOWN_TABLE_SELECTOR)) {
        if (!(element instanceof HTMLTableElement)) {
            continue;
        }
        const column = element.dataset['sortColumn'];
        const direction = element.dataset['sortDirection'];
        if (column === undefined && direction === undefined) {
            continue;
        }
        if (!column || !direction) {
            throw new Error('Assistant Markdown table serialization found incomplete sort state');
        }
        restoreMarkdownTableSourceOrder(element);
        delete element.dataset['sortColumn'];
        delete element.dataset['sortDirection'];
        changed = true;
        for (const header of requireSortableHeaders(element, 'Assistant Markdown table', MARKDOWN_TABLE_HEADER_SELECTOR)) {
            if (header.header.classList.contains('is-active') || header.header.getAttribute('aria-sort') !== 'none' || header.indicator.childNodes.length > 0) {
                changed = true;
            }
            header.header.classList.remove('is-active');
            header.header.setAttribute('aria-sort', 'none');
            header.indicator.replaceChildren();
            header.indicator.classList.remove(MARKDOWN_TABLE_INDICATOR_OVERLAY_CLASS);
        }
    }
    return changed;
};

export { collectMarkdownTableSortState, hasMarkdownTableSortState, normalizeSerializedMarkdownTableSortState, restoreMarkdownTableSortState };
export type { MarkdownTableSortState };
