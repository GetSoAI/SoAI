/* SoAI - Hardware page candlestick interval manager [frontend/assets/ts/pages/hardware/state/history/hardwareCandlestickIntervalManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwarePageState } from '@pages/hardware/state/state.ts';

const resolveHardwareStateCandlestickIntervalMs = (state: HardwarePageState): number => {
    const metadataInterval = Number(state.candlestickMetadata?.intervalMs);
    if (Number.isFinite(metadataInterval) && metadataInterval > 0) {
        return Math.max(1, Math.round(metadataInterval));
    }
    const resolvedInterval = Number(state.lastResolvedCandlestickIntervalMs);
    if (Number.isFinite(resolvedInterval) && resolvedInterval > 0) {
        return Math.max(1, Math.round(resolvedInterval));
    }
    const monitoringInterval = Number(state.monitoringIntervalMs);
    if (Number.isFinite(monitoringInterval) && monitoringInterval > 0) {
        return Math.max(1, Math.round(monitoringInterval));
    }
    throw new TypeError('Unable to resolve candlestick interval');
};

const applyHardwareCandlestickIntervalMetadata = (state: HardwarePageState, intervalMs: number): void => {
    if (!Number.isFinite(intervalMs) || intervalMs <= 0) {
        throw new TypeError('Hardware candlestick interval must be positive');
    }
    state.lastResolvedCandlestickIntervalMs = Math.max(1, Math.round(intervalMs));
    state.candlestickMetadata = {
        ...(state.candlestickMetadata ?? {}),
        intervalMs: state.lastResolvedCandlestickIntervalMs
    };
};

export { applyHardwareCandlestickIntervalMetadata, resolveHardwareStateCandlestickIntervalMs };
