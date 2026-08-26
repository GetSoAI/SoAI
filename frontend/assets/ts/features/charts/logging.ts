/* SoAI - Charts feature logging [frontend/assets/ts/features/charts/logging.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { createModuleLogger, ensureDiagnostics } from '@core/runtime/runtimeContext.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { isFunction } from '@core/typeGuards.ts';

interface ChartLogger {
    info(message: string, detail?: TelemetryValue): void;
    warn(message: string, detail?: TelemetryValue): void;
    error(message: string, detail?: TelemetryValue): void;
    debug(message: string, detail?: TelemetryValue): void;
    log(level?: string, message?: string, detail?: TelemetryValue): void;
}

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LoggerOptions {
    defaultLevel?: LogLevel;
}

const noopLogger: ChartLogger = {
    info(): void {},
    warn(): void {},
    error(): void {},
    debug(): void {},
    log(): void {}
};

const isLogLevel = (level: string | undefined): level is LogLevel => level === 'debug' || level === 'info' || level === 'warn' || level === 'error';

const createChartLogger = (scopeName: string, options: LoggerOptions = {}): ChartLogger => {
    const logFunctionValue = createModuleLogger(scopeName, options.defaultLevel ? { defaultLevel: options.defaultLevel } : {});
    if (!isFunction(logFunctionValue)) {
        return noopLogger;
    }
    const defaultLevel: LogLevel = options.defaultLevel ?? 'info';
    const call = (level: LogLevel | undefined, message: string | undefined, detail: TelemetryValue): void => {
        logFunctionValue(level ?? defaultLevel, message ?? '', detail);
    };
    return {
        info(message: string, detail?: TelemetryValue): void {
            call('info', message, detail);
        },
        warn(message: string, detail?: TelemetryValue): void {
            call('warn', message, detail);
        },
        error(message: string, detail?: TelemetryValue): void {
            call('error', message, detail);
        },
        debug(message: string, detail?: TelemetryValue): void {
            call('debug', message, detail);
        },
        log(level: string = defaultLevel, message?: string, detail?: TelemetryValue): void {
            call(isLogLevel(level) ? level : defaultLevel, message, detail);
        }
    };
};

type DiagnosticsOptions = import('@core/runtime/runtimeContext.ts').DiagnosticsOptions;
type DiagnosticsResult = import('@core/moduleContext.ts').DiagnosticsResult;

const createChartDiagnostics = (name: string, options: DiagnosticsOptions = {}): DiagnosticsResult => ensureDiagnostics(name, options);

const getChartErrorHandler = (): typeof errorHandler => errorHandler;

export { createChartDiagnostics, createChartLogger, getChartErrorHandler };
export type { ChartLogger, LoggerOptions, DiagnosticsOptions };
