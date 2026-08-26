/* SoAI - Metrics page actions [frontend/assets/ts/pages/metrics/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const METRICS_ACTION_EXPORT = 'metrics.export';
export const METRICS_ACTION_SORT = 'metrics.sort';
export const METRICS_ACTION_MORE = 'metrics.more';
export const METRICS_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE = 'metrics.requestDistribution.sourceToggle';
export const METRICS_REQUEST_DISTRIBUTION_SOURCE_TOGGLE_ID = 'metricsRequestDistributionSourceToggle';
export const METRICS_REQUEST_DISTRIBUTION_TITLE_ID = 'metricsRequestDistributionTitle';

export type MetricsActionId = typeof METRICS_ACTION_EXPORT | typeof METRICS_ACTION_SORT | typeof METRICS_ACTION_MORE | typeof METRICS_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE;

const { guard: isMetricsActionId } = createActionIdSet(METRICS_ACTION_EXPORT, METRICS_ACTION_SORT, METRICS_ACTION_MORE, METRICS_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE);

export { isMetricsActionId };
