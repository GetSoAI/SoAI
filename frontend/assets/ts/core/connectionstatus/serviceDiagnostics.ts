/* SoAI - Shared frontend connection status service diagnostics [frontend/assets/ts/core/connectionstatus/serviceDiagnostics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { readQueueDepth } from '@core/connectionstatus/deps.ts';
import { emitConnectionStatusError, publishConnectionStatusMetric } from '@core/connectionstatus/effects.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ConnectionStatusState } from '@core/connectionstatus/state.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface ConnectionStatusTelemetryEmitter {
    (stage: string, message: string, severity: 'debug' | 'info' | 'warn' | 'error', data?: JsonValue, options?: { queueDepth?: number | null }): void;
}

const readConnectionStatusQueueDepth = (moduleName: string): number | null => {
    try {
        return readQueueDepth();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.debug(moduleName, 'Failed to read stream queue depth', runtimeError);
        return null;
    }
};

const emitConnectionStatusServiceError = (state: ConnectionStatusState, error: Error, reason: string, readCurrentQueueDepth: () => number | null, emitTelemetry: ConnectionStatusTelemetryEmitter): void => {
    emitConnectionStatusError(state, error, reason, readCurrentQueueDepth, (stage, message, severity, data, options = {}) => {
        emitTelemetry(stage, message, severity, data, options);
    });
};

const publishStatusMetricState = (state: ConnectionStatusState, stage: string, extra: JsonObject = {}, queueDepth: number | null = null): void => {
    publishConnectionStatusMetric(state, stage, extra, queueDepth);
};

export { emitConnectionStatusServiceError, publishStatusMetricState, readConnectionStatusQueueDepth };
