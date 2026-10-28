/* SoAI - SoAIBench hardware page history table DOM [frontend/assets/ts/features/hardware/modals/soaibenchhistory/pageTableDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { captureReorderMotion } from '@core/animations/reorderMotion.ts';
import { getDocument } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireSortableHeaders, updateSortableTableIndicators, type SortState } from '@core/ui/tables/sortableTable.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { SOAIBENCH_HISTORY_COLUMNS } from '@features/hardware/modals/soaibenchhistory/columns.ts';
import { createActionsCell, createHistoryHeaderCell, createHistoryRunRow, createHistoryValueCell } from '@features/hardware/modals/soaibenchhistory/dom.ts';
import { formatHistoryRows } from '@features/hardware/modals/soaibenchhistory/formatting.ts';
import { createHistoryStateRow, patchHistoryTableRows } from '@features/hardware/modals/soaibenchhistory/rowPatching.ts';
import type { SoAIBenchHistoryModalHost, SoAIBenchHistoryOpenRequest, SoAIBenchHistoryRun } from '@features/hardware/modals/soaibenchhistory/types.ts';

interface PageHistoryEntry {
    request: SoAIBenchHistoryOpenRequest;
    run: SoAIBenchHistoryRun;
}

type PageHistorySortColumn = 'started' | 'gpu' | 'profile' | 'status' | 'score' | 'duration';
type PageHistorySortState = SortState<PageHistorySortColumn>;

const PAGE_COLUMN_KEYS: readonly PageHistorySortColumn[] = ['started', 'gpu', 'profile', 'status', 'score', 'duration'];

const createPageHistoryHeader = (): HTMLTableSectionElement => {
    const documentRef = getDocument();
    const head = documentRef.createElement('thead');
    const row = documentRef.createElement('tr');
    for (const key of PAGE_COLUMN_KEYS) {
        if (key === 'gpu') {
            row.appendChild(createHistoryHeaderCell(documentRef, { key, defaultDirection: 'asc', initialDirection: 'none' }));
            continue;
        }
        const column = SOAIBENCH_HISTORY_COLUMNS.find((candidate) => candidate.key === key);
        if (!column) throw new Error(`SoAI Bench history column missing: ${key}`);
        row.appendChild(createHistoryHeaderCell(documentRef, column));
    }
    const actionsHeader = documentRef.createElement('th');
    actionsHeader.textContent = i18n.t('hardware.modals.soaibenchHistory.columns.actions');
    row.appendChild(actionsHeader);
    head.appendChild(row);
    return head;
};

const renderPageHistoryTable = (host: SoAIBenchHistoryModalHost, entries: readonly PageHistoryEntry[], sortState: PageHistorySortState, stateText: string | null, busyRunIds: ReadonlySet<string>, animateReorder: boolean): void => {
    const root = host.requireHTMLElement('#hardware-soaibench-history-panel');
    const table = host.requireHTMLElement('#hardware-soaibench-history-page-table', root);
    if (!(table instanceof HTMLTableElement)) throw new TypeError('SoAI Bench page history table must be a table');
    let head = table.tHead;
    if (!head) {
        head = createPageHistoryHeader();
        table.appendChild(head);
    }
    const body = table.tBodies[0] ?? table.createTBody();
    const documentRef = getDocument();
    const displayRows = formatHistoryRows(entries.map((entry) => entry.run));
    const rows = entries.map((entry, index) => {
        const display = displayRows[index];
        if (!display) throw new Error('SoAI Bench history display row missing');
        const row = createHistoryRunRow(documentRef, display.runId, index);
        row.dataset['deviceId'] = entry.request.deviceId;
        const values = [display.columns[0], entry.request.gpuName, display.columns[1], display.columns[2], display.columns[3], display.columns[9]];
        for (const [columnIndex, value] of values.entries()) {
            const cell = createHistoryValueCell(documentRef, value ?? '', columnIndex === 3 ? display.statusClassName : null);
            if (value) setTooltipText(cell, value);
            row.appendChild(cell);
        }
        row.appendChild(createActionsCell(documentRef, host, display, busyRunIds.has(display.runId)));
        return row;
    });
    if (stateText !== null) rows.push(createHistoryStateRow(documentRef, PAGE_COLUMN_KEYS.length + 1, 'metrics-table-state', stateText));
    const motion = animateReorder ? captureReorderMotion(body) : null;
    patchHistoryTableRows(body, rows);
    updateSortableTableIndicators({ headers: requireSortableHeaders(table, 'SoAI Bench page history'), activeColumn: sortState.column, activeDirection: sortState.direction, host });
    motion?.play();
};

export { PAGE_COLUMN_KEYS, renderPageHistoryTable };
export type { PageHistoryEntry, PageHistorySortState };
