/* SoAI - SoAI Bench history modal DOM contracts [frontend/assets/ts/features/hardware/modals/soaibenchhistory/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { dom } from '@core/dom/dom.ts';
import { requireButtonElement, requireTableElement } from '@core/dom/typedElements.ts';
import { getDocument } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { requireSortableHeaders, resolveSortableAriaSortValue, updateSortableTableIndicators } from '@core/ui/tables/sortableTable.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { HARDWARE_SOAIBENCH_HISTORY_MODAL_ID } from '@features/hardware/modals/constants.ts';
import { SOAIBENCH_HISTORY_COLUMNS, resolveSoAIBenchHistoryColumnLabel, type SoAIBenchHistoryColumnDefinition } from '@features/hardware/modals/soaibenchhistory/columns.ts';
import { HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION } from '@features/hardware/modals/soaibenchhistory/constants.ts';
import type { SoAIBenchHistorySortState } from '@features/hardware/modals/soaibenchhistory/sorting.ts';
import type { SoAIBenchHistoryDisplayRow, SoAIBenchHistoryModalHost } from '@features/hardware/modals/soaibenchhistory/types.ts';

const SELECTORS: {
    content: string;
    copyButton: string;
    downloadButton: string;
    loading: string;
    rows: string;
    table: string;
    wrapper: string;
} = {
    content: modalUiSelector(HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, 'content'),
    copyButton: modalUiSelector(HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, 'copy'),
    downloadButton: modalUiSelector(HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, 'download'),
    loading: '.hardware-soaibench-history-loading',
    rows: modalUiSelector(HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, 'rows'),
    table: modalUiSelector(HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, 'table'),
    wrapper: modalUiSelector(HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, 'table-wrapper')
};

interface HistoryTableElements {
    rowsElement: HTMLTableSectionElement;
    wrapper: HTMLElement;
}

const requireLoadingOverlay = (host: SoAIBenchHistoryModalHost, modalRoot: HTMLElement): HTMLElement => {
    return host.requireHTMLElement(SELECTORS.loading, modalRoot);
};

const requireCopyButton = (host: SoAIBenchHistoryModalHost, modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButtonElement(host, SELECTORS.copyButton, 'SoAIBench history copy button', modalRoot);
};

const requireDownloadButton = (host: SoAIBenchHistoryModalHost, modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButtonElement(host, SELECTORS.downloadButton, 'SoAIBench history download button', modalRoot);
};

const requireTableElementForModal = (host: SoAIBenchHistoryModalHost, modalRoot: HTMLElement): HTMLTableElement => {
    return requireTableElement(host, SELECTORS.table, SELECTORS.table, modalRoot);
};

const requireContentElement = (host: SoAIBenchHistoryModalHost, modalRoot: HTMLElement): HTMLElement => {
    return host.requireHTMLElement(SELECTORS.content, modalRoot);
};

const createHistoryHeaderCell = (documentRef: Document, column: SoAIBenchHistoryColumnDefinition): HTMLTableCellElement => {
    const label = resolveSoAIBenchHistoryColumnLabel(column.key);
    const header = documentRef.createElement('th');
    header.className = column.initialDirection === 'none' ? 'sortable' : 'sortable is-active';
    header.dataset['action'] = HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION;
    header.dataset['sort'] = column.key;
    header.tabIndex = 0;
    header.setAttribute('role', 'columnheader');
    header.setAttribute('aria-sort', resolveSortableAriaSortValue(column.initialDirection));
    header.setAttribute('aria-label', label);
    setTooltipText(header, label);
    const labelElement = documentRef.createElement('span');
    labelElement.className = 'hardware-soaibench-history-table-label';
    labelElement.textContent = label;
    const sortIndicator = documentRef.createElement('span');
    sortIndicator.className = 'sort-indicator';
    header.appendChild(labelElement);
    header.appendChild(sortIndicator);
    return header;
};

const createHistoryActionsHeaderCell = (documentRef: Document): HTMLTableCellElement => {
    const label = i18n.t('hardware.modals.soaibenchHistory.columns.actions');
    const header = documentRef.createElement('th');
    header.setAttribute('role', 'columnheader');
    header.setAttribute('aria-label', label);
    setTooltipText(header, label);
    const labelElement = documentRef.createElement('span');
    labelElement.className = 'hardware-soaibench-history-table-label';
    labelElement.textContent = label;
    header.appendChild(labelElement);
    return header;
};

const createHistoryTableElements = (): HistoryTableElements => {
    const documentRef = getDocument();
    const wrapper = documentRef.createElement('div');
    wrapper.className = 'metrics-card-content metrics-card-content--table data-table-wrapper hardware-soaibench-history-card-content hardware-soaibench-history-table-wrapper has-scroll';
    wrapper.id = modalUiId(HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, 'table-wrapper');
    wrapper.setAttribute('data-card-content', '');
    const table = documentRef.createElement('table');
    table.className = 'table table-hover table-compact hardware-soaibench-history-table';
    table.id = modalUiId(HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, 'table');
    const header = documentRef.createElement('thead');
    const headerRow = documentRef.createElement('tr');
    for (const column of SOAIBENCH_HISTORY_COLUMNS) {
        headerRow.appendChild(createHistoryHeaderCell(documentRef, column));
    }
    headerRow.appendChild(createHistoryActionsHeaderCell(documentRef));
    const rowsElement = documentRef.createElement('tbody');
    rowsElement.id = modalUiId(HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, 'rows');
    header.appendChild(headerRow);
    table.appendChild(header);
    table.appendChild(rowsElement);
    wrapper.appendChild(table);
    return { rowsElement, wrapper };
};

const resolveHistoryTableElements = (modalRoot: HTMLElement): HistoryTableElements | null => {
    const wrapper = dom.resolve(SELECTORS.wrapper, modalRoot);
    const rowsElement = dom.resolve(SELECTORS.rows, modalRoot);
    if (!(wrapper instanceof HTMLElement) || !(rowsElement instanceof HTMLTableSectionElement)) {
        return null;
    }
    return { rowsElement, wrapper };
};

const syncSortIndicators = (host: SoAIBenchHistoryModalHost, modalRoot: HTMLElement, sortState: SoAIBenchHistorySortState): void => {
    updateSortableTableIndicators({
        headers: requireSortableHeaders(requireTableElementForModal(host, modalRoot), 'SoAIBench history'),
        activeColumn: sortState.column,
        activeDirection: sortState.direction,
        host
    });
};

const setLoadingVisible = (host: SoAIBenchHistoryModalHost, modalRoot: HTMLElement, visible: boolean): void => {
    const overlay = requireLoadingOverlay(host, modalRoot);
    if (visible) {
        host.removeClassName(overlay, 'u-hidden');
        return;
    }
    host.addClassName(overlay, 'u-hidden');
};

const setFooterActionsDisabled = (host: SoAIBenchHistoryModalHost, modalRoot: HTMLElement, disabled: boolean): void => {
    for (const button of [requireCopyButton(host, modalRoot), requireDownloadButton(host, modalRoot)]) {
        button.disabled = disabled;
        button.setAttribute('aria-disabled', disabled ? 'true' : 'false');
    }
};

const createActionButton = (documentRef: Document, host: SoAIBenchHistoryModalHost, action: string, runId: string, iconName: 'copy' | 'download', className: string, label: string): HTMLButtonElement => {
    const button = documentRef.createElement('button');
    button.type = 'button';
    button.className = className;
    button.dataset['action'] = action;
    button.dataset['runId'] = runId;
    button.setAttribute('aria-label', label);
    setTooltipText(button, label);
    host.setHTML(button, host.getIconSync(iconName, { strokeWidth: iconName === 'copy' ? 1 : 1.5 }));
    return button;
};

const createActionsCell = (documentRef: Document, host: SoAIBenchHistoryModalHost, row: SoAIBenchHistoryDisplayRow): HTMLTableCellElement => {
    const cell = documentRef.createElement('td');
    cell.className = 'hardware-soaibench-history-actions-cell';
    const group = documentRef.createElement('div');
    group.className = 'hardware-soaibench-history-row-actions';
    group.appendChild(createActionButton(documentRef, host, HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION, row.runId, 'copy', 'ui-round-button ui-round-button--inline ui-round-button--copy', i18n.t('hardware.modals.soaibenchHistory.ariaLabels.copyRun')));
    group.appendChild(createActionButton(documentRef, host, HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION, row.runId, 'download', 'ui-round-button ui-round-button--inline hardware-soaibench-history-download-round-btn', i18n.t('hardware.modals.soaibenchHistory.ariaLabels.downloadRun')));
    cell.appendChild(group);
    return cell;
};

const resetHistoryState = (host: SoAIBenchHistoryModalHost, modalRoot: HTMLElement): void => {
    const content = requireContentElement(host, modalRoot);
    content.replaceChildren();
    setLoadingVisible(host, modalRoot, true);
};

const renderHistoryRows = (host: SoAIBenchHistoryModalHost, modalRoot: HTMLElement, rows: readonly SoAIBenchHistoryDisplayRow[], sortState: SoAIBenchHistorySortState): void => {
    const content = requireContentElement(host, modalRoot);
    const tableElements = resolveHistoryTableElements(modalRoot) ?? createHistoryTableElements();
    const rowsElement = tableElements.rowsElement;
    const documentRef = getDocument();
    rowsElement.replaceChildren();
    if (rows.length <= 0) {
        const rowElement = documentRef.createElement('tr');
        const cell = documentRef.createElement('td');
        cell.colSpan = SOAIBENCH_HISTORY_COLUMNS.length + 1;
        cell.className = 'u-text-center u-text-muted';
        cell.textContent = i18n.t('hardware.modals.soaibenchHistory.empty');
        rowElement.appendChild(cell);
        rowsElement.appendChild(rowElement);
    }
    rows.forEach((row, index) => {
        const rowElement = documentRef.createElement('tr');
        rowElement.className = resolveCheckerboardClass(index);
        for (const column of row.columns) {
            const cell = documentRef.createElement('td');
            cell.textContent = column;
            rowElement.appendChild(cell);
        }
        rowElement.appendChild(createActionsCell(documentRef, host, row));
        rowsElement.appendChild(rowElement);
    });
    if (!content.contains(tableElements.wrapper)) {
        content.appendChild(tableElements.wrapper);
    }
    syncSortIndicators(host, modalRoot, sortState);
};

export { renderHistoryRows, resetHistoryState, setFooterActionsDisabled, setLoadingVisible, syncSortIndicators };
