/* SoAI - Realtime hardware metric resolver actions [frontend/assets/ts/pages/hardware/realtime/hardwarerealtimemetricresolvers/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import { readNonNegativeIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import { isFiniteNumber, isNullOrUndefined } from '@core/typeGuards.ts';
import type { HardwareGpuSnapshot } from '@core/api/contracts/hardwareContracts.ts';
import { getGpuDevices, getGpuOptionId } from '@features/hardware/public.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';
import { STR_GPU } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/constants.ts';
import type { ChartOhlcNumericContract, DeviceSelection } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/types.ts';

export const HARDWARE_REALTIME_METRIC_RESOLVER_ACTION_NOOP = 'hardware.realtimeMetricResolvers.noop';

export type HardwareRealtimeMetricResolverActionId = typeof HARDWARE_REALTIME_METRIC_RESOLVER_ACTION_NOOP;

const hardwareRealtimeMetricResolverActionIds = createActionIdSet(HARDWARE_REALTIME_METRIC_RESOLVER_ACTION_NOOP);

const isHardwareRealtimeMetricResolverActionId = hardwareRealtimeMetricResolverActionIds.guard;

const resolveGpuMetricFromDevice = (metricKey: string | undefined, gpu: HardwareGpuSnapshot, chartOhlc: ChartOhlcNumericContract): number | null => {
    const key = String(metricKey);
    const resolved = (() => {
        switch (key) {
            case 'utilization':
                return chartOhlc.resolveNumeric(gpu.utilization);
            case 'percent_used':
                return chartOhlc.resolveNumeric(gpu.percentUsed);
            case 'temperature':
                return chartOhlc.resolveNumeric(gpu.temperature);
            case 'power_draw_watts':
                return chartOhlc.resolveNumeric(gpu.powerDrawWatts);
            case 'power_limit_watts':
                return chartOhlc.resolveNumeric(gpu.powerLimitWatts);
            case 'core_clock_mhz':
                return chartOhlc.resolveNumeric(gpu.coreClockMhz);
            case 'mem_clock_mhz':
                return chartOhlc.resolveNumeric(gpu.memClockMhz);
            default:
                return null;
        }
    })();

    if (isNullOrUndefined(resolved)) {
        return null;
    }
    if (key === 'utilization' || key === 'percent_used') {
        return isFiniteNumber(resolved) ? clampPercent(resolved) : null;
    }
    return resolved;
};

const resolveGpuMetric = (metricKey: string | undefined, payload: HardwarePageSnapshot, target: DeviceSelection, chartOhlc: ChartOhlcNumericContract): number | null => {
    if (target.type !== STR_GPU) {
        return null;
    }
    const devices = getGpuDevices(payload);
    if (!devices.length) {
        return null;
    }

    const resolvedIndex = readNonNegativeIntegerOrNullValue(target.gpuIndex) ?? 0;
    const device = devices.find((entry, index) => getGpuOptionId(entry, index) === resolvedIndex) ?? devices[0];
    if (!device) {
        return null;
    }

    return resolveGpuMetricFromDevice(metricKey, device, chartOhlc);
};

export { isHardwareRealtimeMetricResolverActionId, resolveGpuMetric, resolveGpuMetricFromDevice };
