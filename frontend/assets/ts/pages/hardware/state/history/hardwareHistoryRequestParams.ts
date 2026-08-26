/* SoAI - Hardware history request parameters [frontend/assets/ts/pages/hardware/state/history/hardwareHistoryRequestParams.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { scaleHistoryChartPointCount } from '@features/charts/public.ts';
import { STR_CPU, STR_DISK, STR_NETWORK, STR_OHLC } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import { resolveGpuHistoryIndex } from '@pages/hardware/state/hardwareSelection.ts';
import type { DeviceSelection, HistoryRequestParameters } from '@pages/hardware/types.ts';

interface BuildHistoryRequestParametersHost {
    getSelectedHistoryTarget(): DeviceSelection;
    resolveSupportedHistoryComponent(component: JsonValue): string;
    getActiveAggregation(): string;
    computeHistoryPoints(rangeMs: number): number;
    getEffectiveCandlestickIntervalMs(): number;
    clampHistoryPoints(points: number, min?: number): number;
    timeRange: number;
    maxRetentionMinutes: number | null;
}

const buildHardwareHistoryRequestParameters = (host: BuildHistoryRequestParametersHost): { parameters: HistoryRequestParameters; pointBudget: number } => {
    const selectedTarget = host.getSelectedHistoryTarget();
    const component = host.resolveSupportedHistoryComponent(selectedTarget.type || STR_CPU);
    const rangeMinutes = Number(host.timeRange);
    if (!Number.isFinite(rangeMinutes) || rangeMinutes <= 0) {
        throw new TypeError('timeRange must be a positive number of minutes');
    }
    const maxRetentionMinutes = host.maxRetentionMinutes;
    const boundedMinutes = maxRetentionMinutes !== null ? Math.min(rangeMinutes, maxRetentionMinutes) : rangeMinutes;
    const rangeMs = Math.max(60_000, Math.round(boundedMinutes * 60_000));
    const aggregation = host.getActiveAggregation();
    const endTimestampMs = Math.round(serverEpochMs());
    const parameters: HistoryRequestParameters = {
        component,
        aggregation,
        points: host.computeHistoryPoints(rangeMs),
        startTsMs: endTimestampMs - rangeMs,
        endTsMs: endTimestampMs
    };
    const gpuIndex = resolveGpuHistoryIndex(selectedTarget);
    if (typeof gpuIndex === 'number' && Number.isInteger(gpuIndex)) {
        parameters.gpuIndex = gpuIndex;
    }
    if ((component === STR_DISK || component === STR_NETWORK) && typeof selectedTarget.identifier === 'string' && selectedTarget.identifier) {
        parameters['identifier'] = selectedTarget.identifier;
    }
    if (aggregation === STR_OHLC) {
        const intervalMs = host.getEffectiveCandlestickIntervalMs();
        if (intervalMs > 0) {
            const bucketCount = Math.ceil(rangeMs / intervalMs);
            const intervalPoints = host.clampHistoryPoints(scaleHistoryChartPointCount(bucketCount * 2), bucketCount);
            if (bucketCount <= intervalPoints) {
                parameters.intervalMs = intervalMs;
            }
            parameters['points'] = intervalPoints;
        }
    }
    parameters['points'] = host.clampHistoryPoints(parameters['points'], parameters['points']);
    return { parameters, pointBudget: parameters['points'] };
};

export { buildHardwareHistoryRequestParameters };
export type { BuildHistoryRequestParametersHost };
