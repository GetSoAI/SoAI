/* SoAI - Realtime hardware metric resolver effects [frontend/assets/ts/pages/hardware/realtime/hardwarerealtimemetricresolvers/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampPercent } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber, isNullOrUndefined } from '@core/typeGuards.ts';
import { normalizeIdentifier, resolveNetworkSpeedEntry, type NetworkSpeedEntry, type NetworkSpeedSnapshot } from '@features/hardware/public.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';
import { STR_DISK, STR_NETWORK } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/constants.ts';
import type { ChartOhlcNumericContract, DeviceSelection } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/types.ts';

const resolveDiskMetric = (metricKey: string | undefined, payload: HardwarePageSnapshot, target: DeviceSelection, chartOhlc: ChartOhlcNumericContract): number | null => {
    if (target.type !== STR_DISK) {
        return null;
    }
    if (typeof target.identifier !== 'string' || !target.identifier) {
        return null;
    }
    const id = normalizeIdentifier(STR_DISK, target.identifier);
    if (!id) {
        return null;
    }

    const entries = payload.disk ?? [];
    const match = entries.find((entry) => typeof entry.deviceId === 'string' && normalizeIdentifier(STR_DISK, entry.deviceId) === id);
    if (!match) {
        return null;
    }

    const key = String(metricKey);
    const resolved = (() => {
        switch (key) {
            case 'percent_used':
                return chartOhlc.resolveNumeric(match.percentUsed);
            case 'used_bytes':
                return chartOhlc.resolveNumeric(match.usedBytes);
            case 'free_bytes':
                return chartOhlc.resolveNumeric(match.freeBytes);
            case 'total_bytes':
                return chartOhlc.resolveNumeric(match.totalBytes);
            default:
                return null;
        }
    })();

    if (isNullOrUndefined(resolved)) {
        return null;
    }
    if (key === 'percent_used') {
        return isFiniteNumber(resolved) ? clampPercent(resolved) : null;
    }
    return resolved;
};

const resolveNetworkMetricSpeedEntry = (sources: readonly (NetworkSpeedSnapshot | undefined)[], interfaceName: string, deviceId: string): NetworkSpeedEntry | null => {
    for (const source of sources) {
        const match = resolveNetworkSpeedEntry(source, interfaceName, deviceId);
        if (match) {
            return match;
        }
    }
    return null;
};

const resolveNetworkMetric = (metricKey: string | undefined, payload: HardwarePageSnapshot, target: DeviceSelection, networkSpeedSources: readonly (NetworkSpeedSnapshot | undefined)[], chartOhlc: ChartOhlcNumericContract): number | null => {
    if (target.type !== STR_NETWORK) {
        return null;
    }
    if (typeof target.identifier !== 'string' || !target.identifier) {
        return null;
    }
    const id = normalizeIdentifier(STR_NETWORK, target.identifier);
    if (!id) {
        return null;
    }

    const byDeviceId = payload.network?.byDeviceId;
    if (!byDeviceId) return null;
    const match = byDeviceId[id];
    if (!match) return null;
    const nameValue = match.name;
    const interfaceName = typeof nameValue === 'string' ? nameValue : null;
    if (!interfaceName) {
        return null;
    }

    const speedEntry = resolveNetworkMetricSpeedEntry(networkSpeedSources, interfaceName, id);
    if (!speedEntry) {
        return null;
    }

    const key = String(metricKey);
    const resolved = key === 'download_mbps' ? chartOhlc.resolveNumeric(speedEntry.downloadMbps) : key === 'upload_mbps' ? chartOhlc.resolveNumeric(speedEntry.uploadMbps) : null;
    if (!isNullOrUndefined(resolved)) {
        return resolved;
    }

    return null;
};

export { resolveDiskMetric, resolveNetworkMetric };
