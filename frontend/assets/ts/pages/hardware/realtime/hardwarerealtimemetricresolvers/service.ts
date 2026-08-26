/* SoAI - Realtime hardware metric resolver service [frontend/assets/ts/pages/hardware/realtime/hardwarerealtimemetricresolvers/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampPercent } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber, isNullOrUndefined } from '@core/typeGuards.ts';
import { resolveGpuMetric } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/actions.ts';
import { STR_DISK, STR_GPU, STR_NETWORK } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/constants.ts';
import { resolveDiskMetric, resolveNetworkMetric } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/effects.ts';
import type { ChartOhlcNumericContract, RealtimeMetricResolverContext } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/types.ts';

const resolveCpuMetric = (metricKey: string | undefined, payload: import('@pages/hardware/types.ts').HardwarePageSnapshot, chartOhlc: ChartOhlcNumericContract): number | null => {
    const cpus = payload.cpus ?? [];

    const key = String(metricKey);
    if (key === 'memory_percent') {
        const memory = payload.memory;
        if (!memory) {
            return null;
        }
        const percentUsed = chartOhlc.resolveNumeric(memory.percentUsed);
        if (isNullOrUndefined(percentUsed)) {
            return null;
        }
        return isFiniteNumber(percentUsed) ? clampPercent(percentUsed) : null;
    }

    if (!cpus.length) {
        return null;
    }

    if (key === 'usage_percent') {
        const values = cpus.map((cpu) => chartOhlc.resolveNumeric(cpu.usagePercent)).filter((value): value is number => isFiniteNumber(value));
        if (!values.length) {
            return null;
        }
        return clampPercent(values.reduce((sum, value) => sum + value, 0) / values.length);
    }

    if (key === 'temperature_celsius') {
        const values = cpus.map((cpu) => chartOhlc.resolveNumeric(cpu.temperatureCelsius)).filter((value): value is number => isFiniteNumber(value));
        return values.length ? Math.max(...values) : null;
    }

    if (key === 'power_draw_watts') {
        const values = cpus.map((cpu) => chartOhlc.resolveNumeric(cpu.powerDrawWatts)).filter((value): value is number => isFiniteNumber(value));
        if (!values.length) {
            return null;
        }
        return values.reduce((sum, value) => sum + value, 0);
    }

    return null;
};

const extractRealtimeMetricValue = ({ metricKey, selectedTarget, payload, networkSpeedSources, chartOhlc }: RealtimeMetricResolverContext): number | null => {
    if (selectedTarget.type === STR_GPU) {
        return resolveGpuMetric(metricKey, payload, selectedTarget, chartOhlc);
    }
    if (selectedTarget.type === STR_DISK) {
        return resolveDiskMetric(metricKey, payload, selectedTarget, chartOhlc);
    }
    if (selectedTarget.type === STR_NETWORK) {
        return resolveNetworkMetric(metricKey, payload, selectedTarget, networkSpeedSources, chartOhlc);
    }
    return resolveCpuMetric(metricKey, payload, chartOhlc);
};

export { extractRealtimeMetricValue };
