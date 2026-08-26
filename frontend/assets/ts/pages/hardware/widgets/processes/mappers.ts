/* SoAI - Hardware page widgets processes mapping [frontend/assets/ts/pages/hardware/widgets/processes/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import type { ProcessDisplayRow, ProcessRecord, ProcessSortColumn, SortDirection } from '@pages/hardware/widgets/processes/types.ts';

const processNumericPropertyBySortColumn: Record<Exclude<ProcessSortColumn, 'name'>, keyof Pick<ProcessDisplayRow, 'pid' | 'cpu' | 'mem' | 'time'>> = {
    pid: 'pid',
    cpu: 'cpu',
    memory: 'mem',
    runtime: 'time'
};

const normalizeProcessRecord = (record: ProcessRecord): ProcessDisplayRow => {
    const name = typeof record.name === 'string' ? record.name : '';
    const pid = readFiniteProcessNumber(record.pid);
    const cpu = readFiniteProcessNumber(record.cpuPercent);
    const mem = readFiniteProcessNumber(record.memoryMb);
    const swap = readFiniteProcessNumber(record.swapMb);
    const time = readFiniteProcessNumber(record.createTimeMs);
    const user = typeof record.username === 'string' ? record.username : '';

    return {
        name,
        pid: pid !== null && pid > 0 ? pid : 0,
        cpu: cpu ?? 0,
        mem: mem ?? 0,
        swap: swap ?? 0,
        swapKnown: record.swapKnown === true,
        user,
        time: time !== null && time > 0 ? time : 0
    };
};

const readFiniteProcessNumber = (value: JsonValue | null | undefined): number | null => {
    return isFiniteNumber(value) && value >= 0 ? value : null;
};

const buildProcessTableCacheKey = (processes: readonly ProcessDisplayRow[], sortColumn: ProcessSortColumn, sortDirection: SortDirection): string => {
    let cacheKey = '';
    for (const processRow of processes) {
        cacheKey += `${processRow.pid}|${processRow.cpu}|${processRow.mem}|${processRow.swap}|${processRow.swapKnown ? 1 : 0}|${processRow.user}|${processRow.name}|${processRow.time};`;
    }
    return `${cacheKey}::${sortColumn}:${sortDirection}`;
};

const selectTopCpuProcess = (processes: readonly ProcessDisplayRow[]): ProcessDisplayRow | null => {
    let topCpuProcess: ProcessDisplayRow | null = null;
    for (const processRow of processes) {
        if (topCpuProcess === null || processRow.cpu > topCpuProcess.cpu) {
            topCpuProcess = processRow;
        }
    }
    return topCpuProcess;
};

const resolveProcessDisplayName = (processRow: ProcessDisplayRow): string => {
    const name = processRow.name.trim();
    return name ? name : i18n.t('hardware.processes.unknownProcess');
};

const sortProcessRows = (processes: readonly ProcessDisplayRow[], column: ProcessSortColumn, direction: SortDirection): ProcessDisplayRow[] => {
    const multiplier = direction === 'asc' ? 1 : -1;
    return [...processes].sort((left, right) => {
        if (column === 'name') {
            return multiplier * left.name.localeCompare(right.name, getCurrentLocale(), { sensitivity: 'base' });
        }
        const propertyKey = processNumericPropertyBySortColumn[column];
        const leftValue = left[propertyKey];
        const rightValue = right[propertyKey];
        return multiplier * ((isFiniteNumber(leftValue) ? leftValue : 0) - (isFiniteNumber(rightValue) ? rightValue : 0));
    });
};

export { buildProcessTableCacheKey, normalizeProcessRecord, resolveProcessDisplayName, selectTopCpuProcess, sortProcessRows };
