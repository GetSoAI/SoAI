/* SoAI - Hardware page process table rendering [frontend/assets/ts/pages/hardware/widgets/processes/processTableRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { getDocument } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { updateSortableTableIndicators, type SortableHeaderRef } from '@core/ui/tables/sortableTable.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { formatProcessCpu, formatProcessMemory, formatProcessRuntime } from '@features/hardware/public.ts';
import { normalizeProcessRecord, resolveProcessDisplayName } from '@pages/hardware/widgets/processes/mappers.ts';
import type { ProcessSortColumn, ProcessTableManagerDependencies, SortDirection } from '@pages/hardware/widgets/processes/types.ts';

type ProcessRowRefs = {
    row: HTMLTableRowElement;
    nameCell: HTMLTableCellElement;
    nameSpan: HTMLSpanElement;
    killButton: HTMLButtonElement | null;
    ownerSpan: HTMLSpanElement | null;
    pidCell: HTMLTableCellElement;
    cpuCell: HTMLTableCellElement;
    memCell: HTMLTableCellElement;
    runtimeCell: HTMLTableCellElement;
};

type ProcessTableElements = {
    table: HTMLTableElement;
    tbody: HTMLTableSectionElement;
    summary: HTMLElement;
    headers: readonly SortableHeaderRef[];
};

const ensureKillButton = (documentRef: Document, refs: ProcessRowRefs, pid: number): HTMLButtonElement => {
    if (refs.killButton) {
        return refs.killButton;
    }
    const button = documentRef.createElement('button');
    button.type = 'button';
    button.className = 'process-close-btn';
    button.setAttribute('data-action', 'hardware.process.kill');
    button.setAttribute('data-pid', String(pid));
    const killIcon = documentRef.createElement('span');
    killIcon.setAttribute('aria-hidden', 'true');
    killIcon.textContent = '×';
    button.appendChild(killIcon);
    refs.nameCell.appendChild(button);
    refs.killButton = button;
    return button;
};

const createRowRefs = (documentRef: Document, pid: number, allowKillButtons: boolean): ProcessRowRefs => {
    const row = documentRef.createElement('tr');
    const nameCell = documentRef.createElement('td');
    const nameSpan = documentRef.createElement('span');
    nameSpan.className = 'process-name';
    nameCell.appendChild(nameSpan);

    const pidCell = documentRef.createElement('td');
    const cpuCell = documentRef.createElement('td');
    const memCell = documentRef.createElement('td');
    const runtimeCell = documentRef.createElement('td');

    row.appendChild(nameCell);
    row.appendChild(pidCell);
    row.appendChild(cpuCell);
    row.appendChild(memCell);
    row.appendChild(runtimeCell);

    const refs: ProcessRowRefs = {
        row,
        nameCell,
        nameSpan,
        killButton: null,
        ownerSpan: null,
        pidCell,
        cpuCell,
        memCell,
        runtimeCell
    };

    if (allowKillButtons && pid > 0) {
        refs.killButton = ensureKillButton(documentRef, refs, pid);
    }

    return refs;
};

const updateRowRefs = (documentRef: Document, refs: ProcessRowRefs, processRow: ReturnType<typeof normalizeProcessRecord>, index: number, allowKillButtons: boolean): void => {
    const displayName = resolveProcessDisplayName(processRow);
    if (refs.nameSpan.textContent !== displayName) {
        refs.nameSpan.textContent = displayName;
    }
    setTooltipText(refs.nameSpan, displayName);
    if (allowKillButtons && processRow.pid > 0) {
        const button = ensureKillButton(documentRef, refs, processRow.pid);
        const killLabel = i18n.t('hardware.processes.actions.killTooltip', { name: displayName, pid: processRow.pid });
        setTooltipText(button, killLabel);
        if (button.getAttribute('aria-label') !== killLabel) {
            button.setAttribute('aria-label', killLabel);
        }
    } else if (refs.killButton) {
        refs.killButton.remove();
        refs.killButton = null;
    }

    if (processRow.user) {
        if (!refs.ownerSpan) {
            const owner = documentRef.createElement('span');
            owner.className = 'process-owner u-text-muted';
            refs.nameCell.appendChild(owner);
            refs.ownerSpan = owner;
        }
        const ownerText = ` @${processRow.user}`;
        if (refs.ownerSpan.textContent !== ownerText) {
            refs.ownerSpan.textContent = ownerText;
        }
    } else if (refs.ownerSpan) {
        refs.ownerSpan.remove();
        refs.ownerSpan = null;
    }

    const rowClass = resolveCheckerboardClass(index);
    if (refs.row.className !== rowClass) {
        refs.row.className = rowClass;
    }

    const pidText = String(processRow.pid);
    if (refs.pidCell.textContent !== pidText) refs.pidCell.textContent = pidText;
    const cpuText = formatProcessCpu(processRow.cpu);
    if (refs.cpuCell.textContent !== cpuText) refs.cpuCell.textContent = cpuText;
    const memText = formatProcessMemory(processRow.mem);
    if (refs.memCell.textContent !== memText) refs.memCell.textContent = memText;
    const runtimeText = formatProcessRuntime(processRow.time);
    if (refs.runtimeCell.textContent !== runtimeText) refs.runtimeCell.textContent = runtimeText;
};

const updateSortIndicators = (dependencies: ProcessTableManagerDependencies, elements: ProcessTableElements, sortColumn: ProcessSortColumn, sortDirection: SortDirection, lastSortIndicator: { column: ProcessSortColumn; direction: SortDirection } | null): { column: ProcessSortColumn; direction: SortDirection } | null => {
    const last = lastSortIndicator;
    if (last && last.column === sortColumn && last.direction === sortDirection && elements.table.isConnected) {
        return lastSortIndicator;
    }
    const nextLast = { column: sortColumn, direction: sortDirection };
    updateSortableTableIndicators({
        headers: elements.headers,
        activeColumn: sortColumn,
        activeDirection: sortDirection,
        host: dependencies
    });
    return nextLast;
};

const syncProcessRows = (tbody: HTMLTableSectionElement, rows: readonly HTMLTableRowElement[]): void => {
    rows.forEach((row, index) => {
        if (tbody.children[index] !== row) {
            tbody.insertBefore(row, tbody.children[index] ?? null);
        }
    });
    while (tbody.children.length > rows.length) {
        tbody.lastElementChild?.remove();
    }
};

const renderEmptyState = (options: { dependencies: ProcessTableManagerDependencies; elements: ProcessTableElements; dataReady: boolean; rowsByPid: Map<number, ProcessRowRefs>; emptyRow: HTMLTableRowElement | null; sortColumn: ProcessSortColumn; sortDirection: SortDirection; lastSortIndicator: { column: ProcessSortColumn; direction: SortDirection } | null }): { emptyRow: HTMLTableRowElement; lastSortIndicator: { column: ProcessSortColumn; direction: SortDirection } | null } => {
    const stateText = options.dataReady ? i18n.t('hardware.processes.noActive') : i18n.t('hardware.processes.awaiting');
    const documentRef = getDocument();
    const row = options.emptyRow ?? documentRef.createElement('tr');
    options.elements.tbody.classList.remove('hardware-process-body-loading');
    row.className = '';
    let cell: HTMLTableCellElement | null = row.firstElementChild instanceof HTMLTableCellElement ? row.firstElementChild : null;
    if (!(cell instanceof HTMLTableCellElement)) {
        row.textContent = '';
        cell = documentRef.createElement('td');
        row.appendChild(cell);
    }
    cell.colSpan = 5;
    cell.className = 'u-text-center u-text-muted';
    if (cell.textContent !== stateText) {
        cell.textContent = stateText;
    }
    syncProcessRows(options.elements.tbody, [row]);
    options.dependencies.updateText(options.elements.summary, options.dataReady ? i18n.t('hardware.processes.noneDetected') : i18n.t('hardware.processes.connecting'));
    for (const { row } of options.rowsByPid.values()) {
        row.remove();
    }
    options.rowsByPid.clear();
    const nextLast = updateSortIndicators(options.dependencies, options.elements, options.sortColumn, options.sortDirection, options.lastSortIndicator);
    return { emptyRow: row, lastSortIndicator: nextLast };
};

const renderProcessLoadingState = (options: { dependencies: ProcessTableManagerDependencies; elements: ProcessTableElements; rowsByPid: Map<number, ProcessRowRefs>; emptyRow: HTMLTableRowElement | null; sortColumn: ProcessSortColumn; sortDirection: SortDirection; lastSortIndicator: { column: ProcessSortColumn; direction: SortDirection } | null }): { emptyRow: HTMLTableRowElement; lastSortIndicator: { column: ProcessSortColumn; direction: SortDirection } | null } => {
    const documentRef = getDocument();
    const row = options.emptyRow ?? documentRef.createElement('tr');
    options.elements.tbody.classList.add('hardware-process-body-loading');
    row.className = 'hardware-process-loading-row';
    let cell: HTMLTableCellElement | null = row.firstElementChild instanceof HTMLTableCellElement ? row.firstElementChild : null;
    if (!(cell instanceof HTMLTableCellElement)) {
        row.textContent = '';
        cell = documentRef.createElement('td');
        row.appendChild(cell);
    }
    cell.colSpan = 5;
    cell.className = 'hardware-process-loading-cell';
    if (!(cell.firstElementChild instanceof HTMLSpanElement)) {
        cell.textContent = '';
        const spinner = documentRef.createElement('span');
        spinner.className = 'loading-spinner hardware-process-loading-spinner';
        spinner.setAttribute('aria-hidden', 'true');
        cell.appendChild(spinner);
    }
    syncProcessRows(options.elements.tbody, [row]);
    options.dependencies.updateText(options.elements.summary, i18n.t('hardware.processes.connecting'));
    for (const { row } of options.rowsByPid.values()) {
        row.remove();
    }
    options.rowsByPid.clear();
    const nextLast = updateSortIndicators(options.dependencies, options.elements, options.sortColumn, options.sortDirection, options.lastSortIndicator);
    return { emptyRow: row, lastSortIndicator: nextLast };
};

const renderProcessTable = (options: { dependencies: ProcessTableManagerDependencies; elements: ProcessTableElements; dataReady: boolean; processes: readonly ReturnType<typeof normalizeProcessRecord>[]; topProcess: ReturnType<typeof normalizeProcessRecord> | null; allowKillButtons: boolean; rowsByPid: Map<number, ProcessRowRefs>; emptyRow: HTMLTableRowElement | null; sortColumn: ProcessSortColumn; sortDirection: SortDirection; lastSortIndicator: { column: ProcessSortColumn; direction: SortDirection } | null }): { emptyRow: HTMLTableRowElement | null; lastSortIndicator: { column: ProcessSortColumn; direction: SortDirection } | null } => {
    if (!options.processes.length) {
        return renderEmptyState({
            dependencies: options.dependencies,
            elements: options.elements,
            dataReady: options.dataReady,
            rowsByPid: options.rowsByPid,
            emptyRow: options.emptyRow,
            sortColumn: options.sortColumn,
            sortDirection: options.sortDirection,
            lastSortIndicator: options.lastSortIndicator
        });
    }

    const documentRef = getDocument();
    const alive = new Set<number>();
    const rows: HTMLTableRowElement[] = [];
    options.elements.tbody.classList.remove('hardware-process-body-loading');

    options.processes.forEach((processRow, index) => {
        alive.add(processRow.pid);
        const refs = options.rowsByPid.get(processRow.pid) ?? createRowRefs(documentRef, processRow.pid, options.allowKillButtons);
        options.rowsByPid.set(processRow.pid, refs);
        updateRowRefs(documentRef, refs, processRow, index, options.allowKillButtons);
        rows.push(refs.row);
    });

    for (const [pid, refs] of options.rowsByPid.entries()) {
        if (!alive.has(pid)) {
            refs.row.remove();
            options.rowsByPid.delete(pid);
        }
    }

    syncProcessRows(options.elements.tbody, rows);

    const summaryData = options.topProcess
        ? i18n.t('hardware.processes.summary.topCpu', {
              count: options.processes.length,
              name: resolveProcessDisplayName(options.topProcess),
              cpu: formatProcessCpu(options.topProcess.cpu)
          })
        : i18n.t('hardware.processes.summary.noTopCpu', { count: options.processes.length });
    options.dependencies.updateText(options.elements.summary, summaryData);
    const nextLast = updateSortIndicators(options.dependencies, options.elements, options.sortColumn, options.sortDirection, options.lastSortIndicator);
    return { emptyRow: options.emptyRow, lastSortIndicator: nextLast };
};

export { renderProcessLoadingState, renderProcessTable };
export type { ProcessRowRefs, ProcessTableElements };
