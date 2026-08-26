/* SoAI - Hardware feature widgets effects [frontend/assets/ts/features/hardware/widgets/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { decodeHardwareHistory } from '@core/api/contracts/hardwareContracts.ts';
import { serializeHardwareHistoryRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import type { HardwareHistoryRequest } from '@core/api/contracts/hardwareContractTypes.ts';
import { SCALE_CONFIG, WIDGET_HISTORY_REQUEST_PADDING_MS, type ScaleConfigEntry } from '@features/hardware/widgets/constants.ts';
import type { HardwareSnapshotInput, HistoryResponse, WidgetHistoryRequest } from '@features/hardware/widgets/internalContracts.ts';

type WidgetHistoryConfig = HardwareHistoryRequest;

interface WidgetHistoryWindow {
    durationMs: number;
    points: number;
    requestPaddingMs: number;
}

const resolveWidgetHistoryPointCount = (scaleConfig: Readonly<ScaleConfigEntry>, snapshot: HardwareSnapshotInput | null): number => {
    const historyConfig = snapshot?.capabilities?.historyConfig;
    let points = scaleConfig.points;
    const loggingIntervalValue = historyConfig?.loggingIntervalMs;
    const loggingIntervalMs = isFiniteNumber(loggingIntervalValue) && loggingIntervalValue > 0 ? Math.max(1, Math.round(loggingIntervalValue)) : null;
    if (loggingIntervalMs !== null) {
        const requestDurationMs = scaleConfig.durationMs + WIDGET_HISTORY_REQUEST_PADDING_MS;
        points = Math.min(points, Math.ceil(requestDurationMs / loggingIntervalMs));
    }
    const maxPointsValue = historyConfig?.maxPoints;
    const maxPoints = isFiniteNumber(maxPointsValue) && maxPointsValue > 0 ? Math.max(1, Math.round(maxPointsValue)) : null;
    if (maxPoints !== null) {
        points = Math.min(points, maxPoints);
    }
    return Math.max(1, Math.round(points));
};

const createHistoryConfig = (request: WidgetHistoryRequest): WidgetHistoryConfig => {
    const config: WidgetHistoryConfig = {
        component: request.component,
        startTsMs: request.startTsMs,
        endTsMs: request.endTsMs,
        points: request.points
    };

    if (request.component === 'gpu' && isFiniteNumber(request.gpuIndex)) {
        return { ...config, gpuIndex: request.gpuIndex };
    }
    if (request.component === 'network' && request.identifier) {
        return { ...config, identifier: request.identifier };
    }

    return config;
};

const getHistoryWindow = (snapshot: HardwareSnapshotInput | null = null): WidgetHistoryWindow | null => {
    const scaleConfig = SCALE_CONFIG['5m'];
    if (!scaleConfig) {
        return null;
    }

    return {
        durationMs: scaleConfig.durationMs,
        points: resolveWidgetHistoryPointCount(scaleConfig, snapshot),
        requestPaddingMs: WIDGET_HISTORY_REQUEST_PADDING_MS
    };
};

const fetchWidgetHistory = async (request: WidgetHistoryRequest): Promise<HistoryResponse | null> => {
    if (request.signal.aborted) {
        return null;
    }
    const payload = await requestWebSocketSnapshotRecord('hardware.history', serializeHardwareHistoryRequest(createHistoryConfig(request)));
    if (request.signal.aborted) {
        return null;
    }
    return decodeHardwareHistory(payload);
};

export { getHistoryWindow, fetchWidgetHistory };
