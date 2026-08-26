/* SoAI - Shared frontend module context [frontend/assets/ts/core/moduleContext.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createModuleLoggerFactory, createSafeInvoker, type LoggerOptions, type ModuleLoggerFactory, type SafeInvoker } from '@core/diagnostics.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';
type ModuleLogger = (level: LogLevel, message: string, data?: TelemetryValue) => void;

interface DiagnosticsOptions {
    timeoutMs?: number | undefined;
    defaultLevel?: LogLevel | undefined;
}

interface DiagnosticsResult {
    context: string;
    timeoutMs: number | undefined;
    defaultLevel: LogLevel;
}

let loggerFactory: ModuleLoggerFactory | null = null;

const getLoggerFactory = (): ModuleLoggerFactory => {
    if (loggerFactory === null) {
        loggerFactory = createModuleLoggerFactory();
    }
    return loggerFactory;
};

const createModuleLogger = (context: string, options: LoggerOptions = {}): ModuleLogger => getLoggerFactory()(context, options);

const normalizeLogLevel = (value: string | undefined, fallback: LogLevel): LogLevel => {
    if (value === 'debug' || value === 'info' || value === 'warn' || value === 'error') {
        return value;
    }
    return fallback;
};

const createDiagnostics = (context: string, options: DiagnosticsOptions = {}): DiagnosticsResult => {
    const timeoutCandidate = options.timeoutMs;
    const timeoutMs = typeof timeoutCandidate === 'number' && Number.isFinite(timeoutCandidate) && timeoutCandidate > 0 ? timeoutCandidate : undefined;
    const defaultLevel = normalizeLogLevel(options.defaultLevel, 'warn');

    return {
        context,
        timeoutMs,
        defaultLevel
    };
};

export { createDiagnostics, createModuleLogger, createSafeInvoker };

export type { LogLevel, ModuleLogger, SafeInvoker, DiagnosticsOptions, DiagnosticsResult };
