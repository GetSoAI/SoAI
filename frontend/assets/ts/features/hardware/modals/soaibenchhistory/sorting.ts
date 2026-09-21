/* SoAI - SoAI Bench history modal sorting [frontend/assets/ts/features/hardware/modals/soaibenchhistory/sorting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getResolvedLocalizationLocale } from '@core/localization/public.ts';
import { resolveNextSortState, type SortDirection } from '@core/ui/tables/sortableTable.ts';
import { SOAIBENCH_HISTORY_COLUMNS, resolveHistoryColumnDefaultDirection, type SoAIBenchHistorySortColumn } from '@features/hardware/modals/soaibenchhistory/columns.ts';
import type { SoAIBenchHistoryRun } from '@features/hardware/modals/soaibenchhistory/types.ts';

type SoAIBenchHistorySortState = { column: SoAIBenchHistorySortColumn; direction: SortDirection };

const HISTORY_SORT_COLUMNS: readonly SoAIBenchHistorySortColumn[] = Object.freeze(SOAIBENCH_HISTORY_COLUMNS.map((column) => column.key));
const HISTORY_SORT_DEFAULT_STATE: SoAIBenchHistorySortState = { column: 'started', direction: 'desc' };

const compareText = (left: string | null, right: string | null): number => {
    const leftText = left ? left.trim() : '';
    const rightText = right ? right.trim() : '';
    if (!leftText && !rightText) {
        return 0;
    }
    if (!leftText) {
        return 1;
    }
    if (!rightText) {
        return -1;
    }
    return leftText.localeCompare(rightText, getResolvedLocalizationLocale(), { numeric: true, sensitivity: 'base' });
};

const compareNullableNumber = (left: number | null, right: number | null): number => {
    if (left === null && right === null) {
        return 0;
    }
    if (left === null) {
        return 1;
    }
    if (right === null) {
        return -1;
    }
    return left - right;
};

const compareBoolean = (left: boolean, right: boolean): number => Number(left) - Number(right);

const resolveReasonText = (run: SoAIBenchHistoryRun): string | null => {
    return run.failureReason || run.unsupportedReason || (run.staleHardware ? 'stale' : null);
};

const resolveCertificationText = (run: SoAIBenchHistoryRun): string | null => {
    if (run.profile !== 'standard') {
        return null;
    }
    if (run.legacy) {
        return 'legacy';
    }
    if (run.benchmarkMode !== 'certified') {
        return 'quick';
    }
    return run.leaderboardEligible ? 'certified' : `ineligible:${run.leaderboardRejectionReason || ''}`;
};

const compareRuns = (left: SoAIBenchHistoryRun, right: SoAIBenchHistoryRun, column: SoAIBenchHistorySortColumn): number => {
    switch (column) {
        case 'profile':
            return compareText(left.profile, right.profile);
        case 'status':
            return compareText(left.status, right.status);
        case 'score':
            return compareNullableNumber(left.telemetry.overallScore, right.telemetry.overallScore);
        case 'phases': {
            const latencyCompare = compareNullableNumber(left.telemetry.latencyScore, right.telemetry.latencyScore);
            return latencyCompare !== 0 ? latencyCompare : compareNullableNumber(left.telemetry.computeGops, right.telemetry.computeGops);
        }
        case 'stability':
            return compareNullableNumber(left.scoreVariancePercent, right.scoreVariancePercent);
        case 'certification':
            return compareText(resolveCertificationText(left), resolveCertificationText(right));
        case 'temperature':
            return compareNullableNumber(left.telemetry.maxTemperatureCelsius, right.telemetry.maxTemperatureCelsius);
        case 'power': {
            const avgCompare = compareNullableNumber(left.telemetry.avgPowerWatts, right.telemetry.avgPowerWatts);
            return avgCompare !== 0 ? avgCompare : compareNullableNumber(left.telemetry.maxPowerWatts, right.telemetry.maxPowerWatts);
        }
        case 'duration':
            return compareNullableNumber(left.durationMs, right.durationMs);
        case 'started':
            return compareNullableNumber(left.startedAtMs, right.startedAtMs);
        case 'match':
            return compareText(left.matchBasis, right.matchBasis);
        case 'settings':
            return compareBoolean(left.settingsSnapshotAvailable, right.settingsSnapshotAvailable);
        case 'stale':
            return compareBoolean(left.staleHardware, right.staleHardware);
        case 'reason':
            return compareText(resolveReasonText(left), resolveReasonText(right));
    }
};

const sortHistoryRuns = (runs: readonly SoAIBenchHistoryRun[], sortState: SoAIBenchHistorySortState): SoAIBenchHistoryRun[] => {
    return runs
        .map((run, index) => ({ run, index }))
        .sort((left, right) => {
            const direction = sortState.direction === 'asc' ? 1 : -1;
            const compare = compareRuns(left.run, right.run, sortState.column);
            if (compare !== 0) {
                return compare * direction;
            }
            return left.index - right.index;
        })
        .map(({ run }) => run);
};

const resolveNextHistorySortState = (current: SoAIBenchHistorySortState, column: SoAIBenchHistorySortColumn): SoAIBenchHistorySortState => {
    return resolveNextSortState(current, column, resolveHistoryColumnDefaultDirection(column));
};

export { HISTORY_SORT_COLUMNS, HISTORY_SORT_DEFAULT_STATE, resolveNextHistorySortState, sortHistoryRuns };
export type { SoAIBenchHistorySortColumn, SoAIBenchHistorySortState };
