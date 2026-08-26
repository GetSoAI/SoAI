/* SoAI - Shared telemetry mappers [frontend/assets/ts/core/telemetry/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireErrorMessage } from '@core/errors/coerce.ts';
import { filterTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { hasOwn, isFiniteNumber, isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { Severity, TelemetryEvent, TelemetryEventInput, TelemetryValue } from '@core/telemetry/contracts.ts';
import type { TelemetryState } from '@core/telemetry/internalContracts.ts';

const reportFailure = (state: TelemetryState, context: string, error: Error): void => {
    if (isFunction(state.failureReporter)) {
        state.suppressedNotifications += 1;
        try {
            state.failureReporter(context, error);
        } finally {
            state.suppressedNotifications = Math.max(0, state.suppressedNotifications - 1);
        }
        return;
    }
    throw new Error(`[Telemetry] ${context}: ${requireErrorMessage(error, 'Unknown error')}`);
};

const normalizeSeverity = (value: TelemetryValue): Severity => {
    const severity = isString(value) ? value.toLowerCase() : '';
    if (severity === 'debug' || severity === 'info' || severity === 'warn' || severity === 'error' || severity === 'fatal') {
        return severity;
    }
    return 'info';
};

const normalizeEvent = (state: TelemetryState, input: TelemetryEventInput | string): TelemetryEvent => {
    const source: TelemetryEventInput = input && isObject(input) ? input : { message: isString(input) ? input : String(input) };
    const tags = filterTrimmedStringArrayValue(source.tags);
    const payload = hasOwn(source, 'data') || hasOwn(source, 'details') ? (source.data !== undefined ? source.data : source.details) : null;
    const stage = isString(source.stage) && source.stage ? source.stage : null;
    const context = source.context && isObject(source.context) ? { ...source.context } : null;
    const duration = isFiniteNumber(source.duration) ? source.duration : null;
    const attempt = isFiniteNumber(source.attempt) ? source.attempt : null;
    const maxAttempts = isFiniteNumber(source.maxAttempts) ? source.maxAttempts : null;
    const queueDepth = isFiniteNumber(source.queueDepth) ? source.queueDepth : null;
    const moduleName = isString(source.module) && source.module ? source.module : 'Unknown';
    const message = isString(source.message) ? source.message : '';
    const severity = normalizeSeverity(source.severity || source.level);
    const timestamp = isFiniteNumber(source.timestamp) && source.timestamp > 0 ? source.timestamp : Date.now();
    state.eventSequence += 1;
    return {
        id: state.eventSequence,
        timestamp,
        severity,
        module: moduleName,
        message,
        stage,
        duration,
        data: payload,
        context,
        tags,
        attempt,
        maxAttempts,
        queueDepth
    };
};

export { normalizeEvent, reportFailure };
