/* SoAI - Hardware page processes service [frontend/assets/ts/pages/hardware/widgets/processes/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareProcessesResource } from '@core/realtime/streammanager/resources/resourceValueContracts.ts';
import { requireSortableColumn, requireSortableHeaders, resolveNextSortState } from '@core/ui/tables/sortableTable.ts';
import { normalizeProcessRecord, selectTopCpuProcess } from '@pages/hardware/widgets/processes/mappers.ts';
import { ProcessKillController } from '@pages/hardware/widgets/processes/processKillController.ts';
import { createProcessRowOrder } from '@pages/hardware/widgets/processes/processRowOrderManager.ts';
import { renderProcessLoadingState, renderProcessTable, type ProcessRowRefs, type ProcessTableElements } from '@pages/hardware/widgets/processes/processTableRendering.ts';
import { PROCESS_SORT_COLUMNS, PROCESS_SORT_DEFAULT_DIRECTIONS } from '@pages/hardware/widgets/processes/ProcessSortDefinitionsWidget.ts';
import type { ProcessRecord, ProcessSortColumn, ProcessTableManagerDependencies, SortDirection } from '@pages/hardware/widgets/processes/types.ts';

class ProcessTableManager {
    readonly #dependencies: ProcessTableManagerDependencies;
    processList: ProcessRecord[] = [];
    dataReady = false;
    canKillProcesses = false;
    sortColumn: ProcessSortColumn = 'cpu';
    sortDirection: SortDirection = 'desc';
    readonly #killController: ProcessKillController;
    #elements: ProcessTableElements | null = null;
    #rowsByPid: Map<number, ProcessRowRefs> = new Map();
    #emptyRow: HTMLTableRowElement | null = null;
    #lastSortIndicator: { column: ProcessSortColumn; direction: SortDirection } | null = null;
    #orderedPids: number[] = [];
    #domRequired = true;
    #processRowsHydrated = true;
    #pendingHydratedRender = false;
    constructor(dependencies: ProcessTableManagerDependencies) {
        if (!dependencies) {
            throw new Error('ProcessTableManager requires dependencies');
        }
        this.#dependencies = dependencies;
        this.#killController = new ProcessKillController(dependencies, {
            canKillProcesses: () => this.canKillProcesses,
            getProcessList: () => this.processList
        });
    }
    initialize(): void {
        const tableCandidate = this.#dependencies.optionalHTMLElement('hardwareProcessTable');
        const tbodyCandidate = this.#dependencies.optionalHTMLElement('hardwareProcessTableBody');
        const summaryCandidate = this.#dependencies.optionalHTMLElement('hardwareProcessSummary');
        if (!(tableCandidate instanceof HTMLTableElement) || !(tbodyCandidate instanceof HTMLTableSectionElement) || !(summaryCandidate instanceof HTMLElement)) {
            if (!this.#domRequired) {
                this.#elements = null;
                return;
            }
            throw new Error('Hardware process table missing');
        }
        this.#elements = {
            table: tableCandidate,
            tbody: tbodyCandidate,
            summary: summaryCandidate,
            headers: requireSortableHeaders(tableCandidate, 'Hardware process table')
        };
    }
    setDomRequired(required: boolean): void {
        this.#domRequired = required;
        if (!required) {
            this.#elements = null;
        }
    }
    handleSortAction(header: Element): void {
        if (!(header instanceof HTMLElement)) {
            throw new Error('Hardware process sort action requires an HTMLElement header');
        }
        const column = requireSortableColumn(PROCESS_SORT_COLUMNS, header.getAttribute('data-sort') ?? '', 'hardware process');
        const nextSort = resolveNextSortState({ column: this.sortColumn, direction: this.sortDirection }, column, PROCESS_SORT_DEFAULT_DIRECTIONS[column]);
        this.sortColumn = nextSort.column;
        this.sortDirection = nextSort.direction;
        this.#dependencies.onSortChanged({ column: this.sortColumn, direction: this.sortDirection });
        this.#orderedPids = [];
        this.renderProcessCard();
    }
    handleKillAction(target: Element): Promise<void> {
        return this.#killController.handleKillAction(target);
    }
    reset(): void {
        this.dataReady = false;
        this.processList = [];
        this.#pendingHydratedRender = false;
        this.renderProcessCard([]);
    }
    setKillPermission(canKillProcesses: boolean): void {
        if (this.canKillProcesses === canKillProcesses) {
            return;
        }
        this.canKillProcesses = canKillProcesses;
        this.renderProcessCard();
    }
    handleSnapshotUpdate(): void {
        this.#killController.handleSnapshotUpdate();
    }
    getProcessCount(): number {
        return this.processList?.length ?? 0;
    }
    handleResourceUpdate(processes: HardwareProcessesResource): void {
        if (processes.length) {
            this.dataReady = true;
            this.processList = processes;
            this.renderProcessCard();
        } else {
            this.dataReady = false;
            this.processList = [];
            this.#pendingHydratedRender = false;
            this.renderProcessCard([]);
        }
    }
    renderProcessCard(processes: ProcessRecord[] = this.processList): void {
        if (!this.#processRowsHydrated && processes.length) {
            this.#pendingHydratedRender = true;
            this.#renderProcessLoadingState();
            return;
        }
        const ordered = createProcessRowOrder(processes, this.sortColumn, this.sortDirection, this.#orderedPids);
        this.#orderedPids = ordered.pids;
        const topProcess = selectTopCpuProcess(ordered.rows);
        this.#renderProcessTable(ordered.rows, topProcess);
    }
    suspendProcessRowsHydration(): void {
        this.#processRowsHydrated = false;
        this.#pendingHydratedRender = false;
    }
    hydrateProcessRows(): void {
        if (this.#processRowsHydrated) {
            return;
        }
        this.#processRowsHydrated = true;
        if (this.#pendingHydratedRender || this.processList.length) {
            this.#pendingHydratedRender = false;
            this.renderProcessCard();
        }
    }
    dispose(): void {
        this.#killController.dispose();
        this.processList = [];
        this.dataReady = false;
        this.sortColumn = 'cpu';
        this.sortDirection = 'desc';
        this.#elements = null;
        this.#rowsByPid.clear();
        this.#emptyRow = null;
        this.#lastSortIndicator = null;
        this.#orderedPids = [];
        this.#processRowsHydrated = true;
        this.#pendingHydratedRender = false;
    }
    #ensureElements(): ProcessTableElements | null {
        if (this.#elements) {
            if (this.#elements.table.isConnected && this.#elements.tbody.isConnected && this.#elements.summary.isConnected) {
                return this.#elements;
            }
            this.#elements = null;
        }
        this.initialize();
        return this.#elements;
    }
    #renderProcessTable(processes: readonly ReturnType<typeof normalizeProcessRecord>[], topProcess: ReturnType<typeof normalizeProcessRecord> | null): void {
        const elements = this.#ensureElements();
        if (!elements) {
            return;
        }
        const updated = renderProcessTable({
            dependencies: this.#dependencies,
            elements,
            dataReady: this.dataReady,
            processes,
            topProcess,
            allowKillButtons: this.canKillProcesses,
            rowsByPid: this.#rowsByPid,
            emptyRow: this.#emptyRow,
            sortColumn: this.sortColumn,
            sortDirection: this.sortDirection,
            lastSortIndicator: this.#lastSortIndicator
        });
        this.#emptyRow = updated.emptyRow;
        this.#lastSortIndicator = updated.lastSortIndicator;
    }
    #renderProcessLoadingState(): void {
        const elements = this.#ensureElements();
        if (!elements) {
            return;
        }
        const updated = renderProcessLoadingState({
            dependencies: this.#dependencies,
            elements,
            rowsByPid: this.#rowsByPid,
            emptyRow: this.#emptyRow,
            sortColumn: this.sortColumn,
            sortDirection: this.sortDirection,
            lastSortIndicator: this.#lastSortIndicator
        });
        this.#emptyRow = updated.emptyRow;
        this.#lastSortIndicator = updated.lastSortIndicator;
    }
}
export { ProcessTableManager };
export type { ProcessTableManagerDependencies };
