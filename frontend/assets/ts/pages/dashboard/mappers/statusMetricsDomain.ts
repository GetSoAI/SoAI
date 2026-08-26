/* SoAI - Dashboard page status metrics domain [frontend/assets/ts/pages/dashboard/mappers/statusMetricsDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { resolveMetricsTotalTokens, type Metrics } from '@features/metrics/public.ts';

interface DashboardStatusMetrics {
    installedPlugins: number;
    installedModels: number;
    totalTokens: number;
    uptimeSeconds: number;
    completedRequests: number;
    failedRequests: number;
    completedFingerprintValue: JsonValue | undefined;
    failedFingerprintValue: JsonValue | undefined;
}

const resolveDashboardUptimeSeconds = (metrics: JsonValue | null | undefined): number => {
    const metricsObject = isObject(metrics) ? metrics : {};
    const genesis = metricsObject['genesis'];
    const genesisObject = isObject(genesis) ? genesis : {};
    const uptimeFromGenesisMs = Number(genesisObject['uptimeMs']);
    return isFiniteNumber(uptimeFromGenesisMs) ? uptimeFromGenesisMs / 1000 : 0;
};

const toMetrics = (metrics: JsonValue): Metrics => (isObject(metrics) ? metrics : {});

const resolveDashboardStatusMetrics = (metrics: JsonValue, installedPlugins: number, installedModels: number): DashboardStatusMetrics => {
    const metricsObject = isObject(metrics) ? metrics : {};
    const director = metricsObject['director'];
    const directorObject = isObject(director) ? director : {};
    const requests = directorObject['requests'];
    const requestsObject = isObject(requests) ? requests : {};
    const completedFingerprintValue = requestsObject['completed'];
    const failedFingerprintValue = requestsObject['failed'];
    return {
        installedPlugins,
        installedModels,
        totalTokens: resolveMetricsTotalTokens(toMetrics(metrics)),
        uptimeSeconds: resolveDashboardUptimeSeconds(metricsObject),
        completedRequests: Number(completedFingerprintValue ?? 0) || 0,
        failedRequests: Number(failedFingerprintValue ?? 0) || 0,
        completedFingerprintValue,
        failedFingerprintValue
    };
};

export { resolveDashboardStatusMetrics, resolveDashboardUptimeSeconds };
export type { DashboardStatusMetrics };
