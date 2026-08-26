/* SoAI - Shared diagnostic reporting [frontend/assets/ts/core/diagnostics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';
type SafeInvokerValue = TelemetryValue | ((...inputArguments: SafeInvokerValue[]) => SafeInvokerValue);

interface ErrorHandlerInterface {
    debug: (context: string, message: string, error?: TelemetryValue) => void;
    info: (context: string, message: string, error?: TelemetryValue) => void;
    warn: (context: string, message: string, error?: TelemetryValue) => void;
    error: (context: string, message: string, error?: TelemetryValue) => void;
}

interface LoggerOptions {
    defaultLevel?: LogLevel;
}

type ModuleLogger = (level: LogLevel, message: string, error?: TelemetryValue) => void;
type ModuleLoggerFactory = (context: string, options?: LoggerOptions) => ModuleLogger;

const createModuleLoggerFactory = (): ModuleLoggerFactory => {
    return (context: string, options: LoggerOptions = {}): ModuleLogger => {
        if (!isString(context) || !context.trim()) {
            throw new TypeError('createModuleLogger requires a non-empty context string');
        }
        const trimmedContext = context.trim();
        const defaultLevel: LogLevel = options.defaultLevel === 'debug' || options.defaultLevel === 'info' || options.defaultLevel === 'warn' || options.defaultLevel === 'error' ? options.defaultLevel : 'error';
        return (level: LogLevel = defaultLevel, message: string, error?: TelemetryValue): void => {
            const resolvedLevel = isString(level) && level.trim() ? level : defaultLevel;
            const reporter = errorHandler[resolvedLevel];
            if (!isFunction(reporter)) {
                throw new Error(`Error handler missing reporter for level ${resolvedLevel}`);
            }
            errorHandler[resolvedLevel](trimmedContext, message, error);
        };
    };
};

type SafeInvoker = <T>(callback: (...inputArguments: SafeInvokerValue[]) => T, inputArguments?: SafeInvokerValue[], message?: string, level?: LogLevel) => T;

const createSafeInvoker =
    (logger: ModuleLogger, defaultLevel: LogLevel = 'error'): SafeInvoker =>
    <T>(callback: (...inputArguments: SafeInvokerValue[]) => T, inputArguments: SafeInvokerValue[] = [], message?: string, level: LogLevel = defaultLevel): T => {
        if (!isFunction(callback)) {
            throw new TypeError('Safe invoker requires a callback function');
        }
        if (!isFunction(logger)) {
            throw new Error('Safe invoker requires a logger function');
        }
        try {
            return callback(...inputArguments);
        } catch (error) {
            const resolvedLevel = isString(level) && level.trim() ? level : defaultLevel;
            const resolvedMessage = isString(message) && message.trim() ? message : 'Invocation failed';
            const runtimeError = ensureError(error);
            logger(resolvedLevel, resolvedMessage, runtimeError);
            throw runtimeError;
        }
    };

export { createModuleLoggerFactory, createSafeInvoker };

export type { LogLevel, ErrorHandlerInterface, LoggerOptions, ModuleLogger, ModuleLoggerFactory, SafeInvoker };
