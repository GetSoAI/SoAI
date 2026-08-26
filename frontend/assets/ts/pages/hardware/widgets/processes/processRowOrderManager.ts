/* SoAI - Hardware page process row order manager [frontend/assets/ts/pages/hardware/widgets/processes/processRowOrderManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeProcessRecord, sortProcessRows } from '@pages/hardware/widgets/processes/mappers.ts';
import type { ProcessRecord, ProcessSortColumn, SortDirection } from '@pages/hardware/widgets/processes/types.ts';

type ProcessDisplayRow = ReturnType<typeof normalizeProcessRecord>;

interface ProcessRowOrder {
    rows: ProcessDisplayRow[];
    pids: number[];
}

const createProcessRowOrder = (processes: readonly ProcessRecord[], sortColumn: ProcessSortColumn, sortDirection: SortDirection, previousPids: readonly number[]): ProcessRowOrder => {
    const normalizedRows = processes.map((entry) => normalizeProcessRecord(entry));
    const sortedRows = sortProcessRows(normalizedRows, sortColumn, sortDirection);
    if (!previousPids.length) {
        return {
            rows: sortedRows,
            pids: sortedRows.map((row) => row.pid)
        };
    }
    const rowsByPid = new Map<number, ProcessDisplayRow>();
    for (const row of sortedRows) {
        rowsByPid.set(row.pid, row);
    }
    const orderedRows: ProcessDisplayRow[] = [];
    for (const pid of previousPids) {
        const row = rowsByPid.get(pid);
        if (row) {
            orderedRows.push(row);
            rowsByPid.delete(pid);
        }
    }
    orderedRows.push(...Array.from(rowsByPid.values()));
    return {
        rows: orderedRows,
        pids: orderedRows.map((row) => row.pid)
    };
};

export { createProcessRowOrder };
export type { ProcessDisplayRow, ProcessRowOrder };
