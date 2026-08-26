/* SoAI - Hardware feature columns [frontend/assets/ts/features/hardware/modals/soaibenchhistory/columns.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';

type SoAIBenchHistorySortColumn = 'profile' | 'status' | 'score' | 'phases' | 'certification' | 'temperature' | 'power' | 'duration' | 'started' | 'match' | 'settings' | 'stale' | 'reason';

interface SoAIBenchHistoryColumnDefinition {
    key: SoAIBenchHistorySortColumn;
    defaultDirection: SortDirection;
    initialDirection: SortDirection | 'none';
}

const SOAIBENCH_HISTORY_COLUMNS: readonly SoAIBenchHistoryColumnDefinition[] = Object.freeze([
    { key: 'profile', defaultDirection: 'asc', initialDirection: 'none' },
    { key: 'status', defaultDirection: 'asc', initialDirection: 'none' },
    { key: 'score', defaultDirection: 'desc', initialDirection: 'none' },
    { key: 'phases', defaultDirection: 'desc', initialDirection: 'none' },
    { key: 'certification', defaultDirection: 'asc', initialDirection: 'none' },
    { key: 'temperature', defaultDirection: 'desc', initialDirection: 'none' },
    { key: 'power', defaultDirection: 'desc', initialDirection: 'none' },
    { key: 'duration', defaultDirection: 'desc', initialDirection: 'none' },
    { key: 'started', defaultDirection: 'desc', initialDirection: 'desc' },
    { key: 'match', defaultDirection: 'asc', initialDirection: 'none' },
    { key: 'settings', defaultDirection: 'desc', initialDirection: 'none' },
    { key: 'stale', defaultDirection: 'desc', initialDirection: 'none' },
    { key: 'reason', defaultDirection: 'asc', initialDirection: 'none' }
]);

const resolveHistoryColumnDefaultDirection = (column: SoAIBenchHistorySortColumn): SortDirection => {
    for (const definition of SOAIBENCH_HISTORY_COLUMNS) {
        if (definition.key === column) {
            return definition.defaultDirection;
        }
    }
    throw new Error(`Unsupported SoAIBench history sort column: ${column}`);
};

const resolveSoAIBenchHistoryColumnLabel = (column: SoAIBenchHistorySortColumn): string => {
    switch (column) {
        case 'profile':
            return i18n.t('hardware.modals.soaibenchHistory.columns.profile');
        case 'status':
            return i18n.t('hardware.modals.soaibenchHistory.columns.status');
        case 'score':
            return i18n.t('hardware.modals.soaibenchHistory.columns.score');
        case 'phases':
            return i18n.t('hardware.modals.soaibenchHistory.columns.phases');
        case 'certification':
            return i18n.t('hardware.modals.soaibenchHistory.columns.certification');
        case 'temperature':
            return i18n.t('hardware.modals.soaibenchHistory.columns.temperature');
        case 'power':
            return i18n.t('hardware.modals.soaibenchHistory.columns.power');
        case 'duration':
            return i18n.t('hardware.modals.soaibenchHistory.columns.duration');
        case 'started':
            return i18n.t('hardware.modals.soaibenchHistory.columns.started');
        case 'match':
            return i18n.t('hardware.modals.soaibenchHistory.columns.match');
        case 'settings':
            return i18n.t('hardware.modals.soaibenchHistory.columns.settings');
        case 'stale':
            return i18n.t('hardware.modals.soaibenchHistory.columns.stale');
        case 'reason':
            return i18n.t('hardware.modals.soaibenchHistory.columns.reason');
    }
    const unhandledColumn: never = column;
    return unhandledColumn;
};

export { SOAIBENCH_HISTORY_COLUMNS, resolveHistoryColumnDefaultDirection, resolveSoAIBenchHistoryColumnLabel };
export type { SoAIBenchHistoryColumnDefinition, SoAIBenchHistorySortColumn };
