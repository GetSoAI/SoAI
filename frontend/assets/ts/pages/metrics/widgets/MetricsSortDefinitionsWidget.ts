/* SoAI - Metrics page sort definitions widget [frontend/assets/ts/pages/metrics/widgets/MetricsSortDefinitionsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeSortDirection, requireSortableColumn, resolveNextSortState, type SortDirection } from '@core/ui/tables/sortableTable.ts';

const PLUGIN_HEALTH_SORT_COLUMNS: readonly string[] = ['name', 'status', 'requests', 'tokens'];
const MODEL_TABLE_SORT_COLUMNS: readonly string[] = ['model', 'requests', 'tokens', 'status'];
const API_KEY_USAGE_SORT_COLUMNS: readonly string[] = ['label', 'prefix', 'status', 'requests', 'rateLimited', 'lastUsed'];
const FRONTEND_TELEMETRY_SORT_COLUMNS: readonly string[] = ['metric', 'value'];
const SYSTEM_STATS_SORT_COLUMNS: readonly string[] = ['metric', 'value'];

const PLUGIN_HEALTH_SORT_DEFAULT_DIRECTIONS: Readonly<Record<string, SortDirection>> = { name: 'asc', status: 'desc', requests: 'desc', tokens: 'desc' };
const MODEL_TABLE_SORT_DEFAULT_DIRECTIONS: Readonly<Record<string, SortDirection>> = { model: 'asc', requests: 'desc', tokens: 'desc', status: 'desc' };
const API_KEY_USAGE_SORT_DEFAULT_DIRECTIONS: Readonly<Record<string, SortDirection>> = { label: 'asc', prefix: 'asc', status: 'asc', requests: 'desc', rateLimited: 'desc', lastUsed: 'desc' };
const FRONTEND_TELEMETRY_SORT_DEFAULT_DIRECTIONS: Readonly<Record<string, SortDirection>> = { metric: 'asc', value: 'asc' };
const SYSTEM_STATS_SORT_DEFAULT_DIRECTIONS: Readonly<Record<string, SortDirection>> = { metric: 'asc', value: 'desc' };

const resolveMetricsNextSortState = (currentColumn: string, currentDirection: string, requestedColumn: string, allowedColumns: readonly string[], defaultDirections: Readonly<Record<string, SortDirection>>, contextLabel: string): { column: string; direction: SortDirection } => {
    const sortColumn = requireSortableColumn(allowedColumns, requestedColumn, contextLabel);
    return resolveNextSortState({ column: currentColumn, direction: normalizeSortDirection(currentDirection) }, sortColumn, defaultDirections[sortColumn] ?? 'asc');
};

export { API_KEY_USAGE_SORT_COLUMNS, API_KEY_USAGE_SORT_DEFAULT_DIRECTIONS, FRONTEND_TELEMETRY_SORT_COLUMNS, FRONTEND_TELEMETRY_SORT_DEFAULT_DIRECTIONS, MODEL_TABLE_SORT_COLUMNS, MODEL_TABLE_SORT_DEFAULT_DIRECTIONS, PLUGIN_HEALTH_SORT_COLUMNS, PLUGIN_HEALTH_SORT_DEFAULT_DIRECTIONS, SYSTEM_STATS_SORT_COLUMNS, SYSTEM_STATS_SORT_DEFAULT_DIRECTIONS, resolveMetricsNextSortState };
