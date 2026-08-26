/* SoAI - Hardware page widgets memory swap mapping [frontend/assets/ts/pages/hardware/widgets/memoryswap/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { formatProcessMemory } from '@features/hardware/public.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';
import { normalizeProcessRecord, resolveProcessDisplayName } from '@pages/hardware/widgets/processes/mappers.ts';
import type { ProcessDisplayRow } from '@pages/hardware/widgets/processes/types.ts';
import type { MemorySwapMode, MemorySwapPanelInput, MemorySwapProcessUsage, MemorySwapRenderModel, MemorySwapUsage } from '@pages/hardware/widgets/memoryswap/types.ts';

const MAX_PROCESS_ROWS = 3;
type MemorySwapUsageSource = HardwarePageSnapshot['memory'] | HardwarePageSnapshot['swap'] | null;

const buildMemorySwapRenderModel = (input: MemorySwapPanelInput): MemorySwapRenderModel => {
    const ramUsage = buildUsage('ram', input.snapshot?.memory ?? null);
    const swapUsage = buildUsage('swap', input.snapshot?.swap ?? null);
    const rows = input.processes.map((process) => normalizeProcessRecord(process));
    const processes = buildProcessUsageRows(input.mode, rows);
    const processStatus = resolveProcessStatus(input, rows, processes);
    return {
        summary: formatTotalMemorySummary(resolveTotalMemoryGb(input)),
        mode: input.mode,
        ramUsage,
        swapUsage,
        processes,
        processMetricLabel: buildProcessMetricLabel(input.mode, rows),
        processStatus
    };
};

const buildUsage = (type: MemorySwapMode, raw: MemorySwapUsageSource): MemorySwapUsage => {
    const totalGb = readFinite(raw?.totalGb ?? null);
    const usedGb = readFinite(raw?.usedGb ?? null);
    const percentSource = readFinite(raw?.percentUsed ?? null) ?? readFinite(raw?.percent ?? null);
    const percent = percentSource === null && totalGb !== null && usedGb !== null && totalGb > 0 ? (usedGb / totalGb) * 100 : percentSource;
    const available = totalGb !== null && totalGb > 0;
    const label = type === 'ram' ? i18n.t('hardware.cards.memorySwap.labels.ram') : i18n.t('hardware.cards.memorySwap.labels.swap');
    return {
        type,
        label,
        percent: clampPercent(percent ?? 0),
        usedText: usedGb !== null ? formatMemoryGigabytes(usedGb) : i18n.t('hardware.cards.memorySwap.unavailableShort'),
        totalText: totalGb !== null ? formatMemoryGigabytes(totalGb) : i18n.t('hardware.cards.memorySwap.unavailableShort'),
        available
    };
};

const formatMemoryGigabytes = (gigabytes: number): string => {
    return formatBytes(gigabytes * 1024 ** 3, 2);
};

const formatMemoryCapacity = (gigabytes: number | null): string => {
    if (gigabytes === null) {
        return i18n.t('hardware.cards.memorySwap.unavailableShort');
    }
    return formatMemoryGigabytes(gigabytes);
};

const formatTotalMemorySummary = (gigabytes: number | null): string => {
    return i18n.t('hardware.cards.memorySwap.summary.totalRamVram', { total: formatMemoryCapacity(gigabytes) });
};

const resolveTotalRamGb = (input: MemorySwapPanelInput): number | null => {
    const summary = isJsonObject(input.snapshot?.summary) ? input.snapshot.summary : {};
    const capabilities = isJsonObject(input.snapshot?.capabilities) ? input.snapshot.capabilities : {};
    return readFinite(summary.totalSystemRamGb ?? null) ?? readFinite(capabilities.systemRamGb ?? null) ?? readFinite(input.snapshot?.memory?.totalGb ?? null);
};

const resolveTotalVramGb = (input: MemorySwapPanelInput): number | null => {
    const summary = isJsonObject(input.snapshot?.summary) ? input.snapshot.summary : {};
    const capabilities = isJsonObject(input.snapshot?.capabilities) ? input.snapshot.capabilities : {};
    return readFinite(summary.totalVramGb ?? null) ?? readFinite(capabilities.totalVramGb ?? null);
};

const resolveTotalMemoryGb = (input: MemorySwapPanelInput): number | null => {
    const summary = isJsonObject(input.snapshot?.summary) ? input.snapshot.summary : {};
    const capabilities = isJsonObject(input.snapshot?.capabilities) ? input.snapshot.capabilities : {};
    const reported = readFinite(summary.totalSystemMemoryGb ?? null) ?? readFinite(capabilities.totalSystemMemoryGb ?? null);
    if (reported !== null) {
        return reported;
    }
    const ram = resolveTotalRamGb(input);
    const vram = resolveTotalVramGb(input);
    if (ram === null || vram === null) {
        return null;
    }
    return ram + vram;
};

const buildProcessUsageRows = (mode: MemorySwapMode, rows: readonly ProcessDisplayRow[]): MemorySwapProcessUsage[] => {
    const candidates = rows
        .map((row) => buildProcessUsageRow(mode, row))
        .filter((row): row is MemorySwapProcessUsage => row !== null)
        .sort((left, right) => right.valueMb - left.valueMb || left.pid - right.pid)
        .slice(0, MAX_PROCESS_ROWS);
    const maxValue = candidates.reduce((max, row) => Math.max(max, row.valueMb), 0);
    return candidates.map((row) => ({
        pid: row.pid,
        name: row.name,
        valueMb: row.valueMb,
        valueText: row.valueText,
        percentOfMax: maxValue > 0 ? clampPercent((row.valueMb / maxValue) * 100) : 0
    }));
};

const buildProcessUsageRow = (mode: MemorySwapMode, row: ProcessDisplayRow): MemorySwapProcessUsage | null => {
    if (mode === 'swap' && !row.swapKnown) {
        return null;
    }
    const valueMb = mode === 'ram' ? row.mem : row.swap;
    if (!isFiniteNumber(valueMb) || valueMb <= 0) {
        return null;
    }
    return {
        pid: row.pid,
        name: resolveProcessDisplayName(row),
        valueMb,
        valueText: formatProcessMemory(valueMb),
        percentOfMax: 0
    };
};

const buildProcessMetricLabel = (mode: MemorySwapMode, rows: readonly ProcessDisplayRow[]): string => {
    if (mode === 'ram') {
        return i18n.t('hardware.cards.memorySwap.processes.activeCount', { count: rows.length });
    }
    return i18n.t('hardware.cards.memorySwap.processes.activeCount', { count: countSwapProcesses(rows) });
};

const countSwapProcesses = (rows: readonly ProcessDisplayRow[]): number => {
    return rows.filter((row) => row.swapKnown && row.swap > 0).length;
};

const resolveProcessStatus = (input: MemorySwapPanelInput, rows: readonly ProcessDisplayRow[], processes: readonly MemorySwapProcessUsage[]): string | null => {
    if (input.snapshot === null) {
        return i18n.t('hardware.cards.memorySwap.states.awaitingSnapshot');
    }
    if (!input.canViewProcesses) {
        return i18n.t('hardware.cards.memorySwap.states.noPermission');
    }
    if (!input.processDataReady) {
        return i18n.t('hardware.cards.memorySwap.states.awaitingProcesses');
    }
    if (input.mode === 'swap' && rows.length > 0 && !hasKnownProcessSwap(rows)) {
        return i18n.t('hardware.cards.memorySwap.states.processSwapUnavailable');
    }
    if (!processes.length) {
        return input.mode === 'ram' ? i18n.t('hardware.cards.memorySwap.states.noProcessUsage') : i18n.t('hardware.cards.memorySwap.states.noSwapProcessUsage');
    }
    return null;
};

const hasKnownProcessSwap = (rows: readonly ProcessDisplayRow[]): boolean => {
    return rows.some((row) => row.swapKnown);
};

const readFinite = (value: JsonValue | number | null | undefined): number | null => {
    return isFiniteNumber(value) && value >= 0 ? value : null;
};

export { buildMemorySwapRenderModel };
