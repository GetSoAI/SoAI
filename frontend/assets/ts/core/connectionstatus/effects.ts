/* SoAI - Shared frontend connection status effects [frontend/assets/ts/core/connectionstatus/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { telemetry } from '@core/telemetry/service.ts';
import { normalizeErrorTelemetryFields } from '@core/errors/coerce.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import { readQueueDepth } from '@core/connectionstatus/deps.ts';
import { METRIC_QD, METRIC_STAT, MODULE_NAME, SRC, type TelemetryOptions, type TelemetrySeverity } from '@core/connectionstatus/constants.ts';
import type { ConnectionStatusState } from '@core/connectionstatus/state.ts';

const copyJsonObject = (value: JsonObject): JsonObject => {
    const copied: JsonObject = {};
    for (const [key, entry] of Object.entries(value)) {
        copied[key] = entry;
    }
    return copied;
};

const normalizeTelemetryData = (data: JsonValue): JsonObject['data'] => {
    if (isJsonObject(data)) return copyJsonObject(data);
    return isJsonValue(data) ? data : null;
};

const emitConnectionStatusTelemetry = (stage: string, message: string, severity: TelemetrySeverity, data: JsonValue, options: TelemetryOptions = {}): void => {
    const durationValue = options.duration;
    const duration = typeof durationValue === 'number' && Number.isFinite(durationValue) ? durationValue : null;
    const payload: JsonObject = {
        module: MODULE_NAME,
        severity,
        stage,
        message,
        data: normalizeTelemetryData(data),
        duration
    };
    const queueDepth = options.queueDepth;
    const attempt = options.attempt;
    const maxAttempts = options.maxAttempts;
    if (typeof queueDepth === 'number' && Number.isFinite(queueDepth)) payload['queueDepth'] = queueDepth;
    if (typeof attempt === 'number' && Number.isFinite(attempt)) payload['attempt'] = attempt;
    if (typeof maxAttempts === 'number' && Number.isFinite(maxAttempts)) payload['maxAttempts'] = maxAttempts;

    telemetry.emit(payload);
};

const publishConnectionStatusMetric = (state: ConnectionStatusState, stage: string, extra: JsonObject = {}, providedDepth: number | null | undefined = undefined): void => {
    const observedDepth = providedDepth !== undefined ? providedDepth : readQueueDepth();
    const queueDepth = isNullOrUndefined(observedDepth) ? null : observedDepth;
    if (queueDepth !== null) {
        state.lastQueueDepth = queueDepth;
        telemetry.publishMetric(METRIC_QD, queueDepth, { source: SRC });
    }

    telemetry.publishMetric(METRIC_STAT, stage, {
        connected: state.connected,
        subscribers: state.subscribers.size,
        restartSubscribers: state.restartSubscribers.size,
        holds: state.connectionHolds.size,
        queueDepth: queueDepth !== null ? queueDepth : state.lastQueueDepth,
        ...extra
    });
};

const emitConnectionStatusError = (state: ConnectionStatusState, error: Error, reason: string, readQueueDepthValue: () => number | null, emitTelemetry: (stage: string, message: string, severity: TelemetrySeverity, data: JsonValue, options?: TelemetryOptions) => void): void => {
    const queueDepth = readQueueDepthValue();
    const payload = {
        reason,
        error: normalizeErrorTelemetryFields(error)
    };
    emitTelemetry('connection:lost', reason, 'warn', payload, { queueDepth });
    publishConnectionStatusMetric(state, 'connection:lost', payload, queueDepth);
};

export { emitConnectionStatusError, emitConnectionStatusTelemetry, publishConnectionStatusMetric };
