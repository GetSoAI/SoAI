/* SoAI - Shared telemetry effects [frontend/assets/ts/core/telemetry/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getGlobalScope } from '@core/environment/public.ts';
import { isFunction, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import type { TelemetryBatch, TelemetryValue } from '@core/telemetry/contracts.ts';
import type { ConsoleSinkState, TelemetryState } from '@core/telemetry/internalContracts.ts';
import { registerSink } from '@core/telemetry/actions.ts';

const resolveConsole = (): ConsoleSinkState => {
    const scope = getGlobalScope();
    const consoleRef = scope.console;
    if (!isObject(consoleRef)) {
        throw new Error('Console is unavailable for telemetry sink');
    }
    return consoleRef;
};

const buildConsoleSink = (): ((batch: TelemetryBatch) => void) => {
    const consoleRef = resolveConsole();
    return (batch: TelemetryBatch): void => {
        if (!isObject(batch) || !Array.isArray(batch.events)) {
            return;
        }
        batch.events.forEach((event) => {
            if (!isObject(event)) {
                return;
            }
            const severity = event.severity || 'info';
            const module = event.module || 'Unknown';
            const message = event.message ?? '';
            const prefix = `[${module}]`;
            const logData: TelemetryValue = !isNullOrUndefined(event.data) ? event.data : null;

            if (severity === 'fatal' || severity === 'error') {
                if (isFunction(consoleRef.error)) {
                    if (logData) {
                        consoleRef.error(prefix, message, logData);
                    } else {
                        consoleRef.error(prefix, message);
                    }
                }
            } else if (severity === 'warn') {
                if (isFunction(consoleRef.warn)) {
                    if (logData) {
                        consoleRef.warn(prefix, message, logData);
                    } else {
                        consoleRef.warn(prefix, message);
                    }
                }
            } else if (severity === 'debug') {
                if (isFunction(consoleRef.debug)) {
                    if (logData) {
                        consoleRef.debug(prefix, message, logData);
                    } else {
                        consoleRef.debug(prefix, message);
                    }
                }
            } else if (isFunction(consoleRef.log)) {
                if (logData) {
                    consoleRef.log(prefix, message, logData);
                } else {
                    consoleRef.log(prefix, message);
                }
            }
        });
    };
};

const ensureConsoleSink = (state: TelemetryState): void => {
    if (state.consoleSinkRegistered) {
        return;
    }
    registerSink(state, 'console', buildConsoleSink(), { includeMetrics: false });
    state.consoleSinkRegistered = true;
};

export { ensureConsoleSink };
