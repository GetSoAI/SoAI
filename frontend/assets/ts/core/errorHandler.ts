/* SoAI - Shared frontend error handler [frontend/assets/ts/core/errorHandler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setTelemetryFailureReporter, telemetry } from '@core/telemetry/service.ts';
import { isArray, isObject, isThenable, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { TelemetryFields, TelemetryValue } from '@core/telemetry/contracts.ts';

type Severity = 'debug' | 'info' | 'warn' | 'error' | 'fatal';
type ErrorHandlerResult = ErrorHandlerValue | Promise<ErrorHandlerValue>;
type ErrorHandlerFunction = (...inputArguments: ErrorHandlerValue[]) => ErrorHandlerResult;
type ErrorHandlerValue = TelemetryValue | ErrorHandlerFunction;

interface EmitOptions {
    stage?: string;
    duration?: number;
    context?: TelemetryFields;
    tags?: string[];
    attempt?: number;
    maxAttempts?: number;
    queueDepth?: number;
}

interface TelemetryPayload {
    severity: Severity;
    module: string;
    message: string;
    data: TelemetryValue;
    stage?: string | undefined;
    duration?: number | undefined;
    context?: TelemetryFields | undefined;
    tags?: string[] | undefined;
    attempt?: number | undefined;
    maxAttempts?: number | undefined;
    queueDepth?: number | undefined;
}

interface HandleErrorOptions {
    module?: string;
    context?: string;
}

type ExecutableFunction = ErrorHandlerFunction;

const emit = (severity: Severity, module: string, message: string, data: TelemetryValue = null, options: EmitOptions = {}): void => {
    const payload: TelemetryPayload = {
        severity,
        module: isString(module) && module ? module : 'Unknown',
        message: isString(message) ? message : '',
        data
    };
    if (isString(options.stage) && options.stage) {
        payload.stage = options.stage;
    }
    if (Number.isFinite(options.duration)) {
        payload.duration = options.duration;
    }
    if (options.context && isObject(options.context)) {
        payload.context = { ...options.context };
    }
    if (isArray(options.tags)) {
        payload.tags = options.tags;
    }
    if (Number.isFinite(options.attempt)) {
        payload.attempt = options.attempt;
    }
    if (Number.isFinite(options.maxAttempts)) {
        payload.maxAttempts = options.maxAttempts;
    }
    if (Number.isFinite(options.queueDepth)) {
        payload.queueDepth = options.queueDepth;
    }
    telemetry.emit(payload);
};

const handleExecution = (functionValue: ExecutableFunction, module: string, context: string, inputArguments: ErrorHandlerValue[]): ErrorHandlerResult => {
    try {
        const result = functionValue(...inputArguments);
        if (isThenable(result)) {
            const monitorExecution = async (): Promise<ErrorHandlerValue> => {
                try {
                    return await result;
                } catch (error) {
                    const runtimeError = ensureError(error);
                    emit('error', module, `${context}: ${runtimeError.message || 'Unknown error'}`, runtimeError);
                    throw runtimeError;
                }
            };
            return monitorExecution();
        }
        return result;
    } catch (error) {
        const runtimeError = ensureError(error);
        emit('error', module, `${context}: ${runtimeError.message || 'Unknown error'}`, runtimeError);
        throw runtimeError;
    }
};

let failureReporterInitialized = false;

const ensureFailureReporter = (): void => {
    if (!failureReporterInitialized) {
        failureReporterInitialized = true;
        setTelemetryFailureReporter((context: string, error: Error) => {
            const consoleRef = globalThis.console;
            if (consoleRef?.warn) {
                consoleRef.warn('[Telemetry]', context, error);
            }
        });
    }
};

class ErrorHandler {
    initialized: boolean;

    constructor() {
        this.initialized = false;
    }

    debug(module: string, message: string, data: TelemetryValue = null, options: EmitOptions = {}): void {
        ensureFailureReporter();
        emit('debug', module, message, data, options);
    }

    info(module: string, message: string, data: TelemetryValue = null, options: EmitOptions = {}): void {
        ensureFailureReporter();
        emit('info', module, message, data, options);
    }

    warn(module: string, message: string, data: TelemetryValue = null, options: EmitOptions = {}): void {
        ensureFailureReporter();
        emit('warn', module, message, data, options);
    }

    error(module: string, message: string, data: TelemetryValue = null, options: EmitOptions = {}): void {
        ensureFailureReporter();
        emit('error', module, message, data, options);
    }

    fatal(module: string, message: string, data: TelemetryValue = null, options: EmitOptions = {}): void {
        ensureFailureReporter();
        emit('fatal', module, message, data, options);
    }

    _handleExecution(functionValue: ExecutableFunction, module: string, context: string, inputArguments: ErrorHandlerValue[]): ErrorHandlerResult {
        ensureFailureReporter();
        return handleExecution(functionValue, module, context, inputArguments);
    }

    safeExecute(functionValue: ExecutableFunction, module: string = 'Unknown', ...inputArguments: ErrorHandlerValue[]): ErrorHandlerResult {
        ensureFailureReporter();
        return handleExecution(functionValue, module, 'Execution failed', inputArguments);
    }

    createError(module: string, message: string, cause: ErrorHandlerValue | null = null): Error {
        if (!cause) {
            return new Error(`[${module}] ${message}`);
        }
        return new Error(`[${module}] ${message}`, { cause });
    }

    wrapTryCatch(functionValue: ExecutableFunction, module: string, context: string = 'Function execution'): ExecutableFunction {
        ensureFailureReporter();
        return (...inputArguments: ErrorHandlerValue[]) => handleExecution(functionValue, module, context, inputArguments);
    }

    handleError(error: Error | null, options: HandleErrorOptions = {}): void {
        ensureFailureReporter();
        const module = options.module || options.context || 'Unknown';
        const message = error?.message || 'Unknown error';
        const emitOptions: EmitOptions = {};
        if (options.context) {
            emitOptions.context = { contextName: options.context };
        }
        emit('error', module, message, error, emitOptions);
    }

    safePromise<T>(promise: Promise<T> | T, module: string, context: string = 'Promise execution'): Promise<T> {
        ensureFailureReporter();
        const handlePromise = async (): Promise<T> => {
            try {
                return await Promise.resolve(promise);
            } catch (error) {
                const runtimeError = ensureError(error);
                const message = `${context}: ${runtimeError.message || 'Unknown error'}`;
                emit('error', module, message, runtimeError);
                throw runtimeError;
            }
        };
        return handlePromise();
    }

    safeAsyncFunctionValue<T extends ErrorHandlerValue[], R>(functionValue: (...inputArguments: T) => Promise<R>, module: string, context: string = 'Async execution'): (...inputArguments: T) => Promise<R> {
        ensureFailureReporter();
        return async (...inputArguments: T): Promise<R> => {
            try {
                return await functionValue(...inputArguments);
            } catch (error) {
                const runtimeError = ensureError(error);
                emit('error', module, `${context}: ${runtimeError.message || 'Unknown error'}`, runtimeError);
                throw runtimeError;
            }
        };
    }
}

const errorHandler = new ErrorHandler();

export { ErrorHandler, errorHandler };

export type { Severity, EmitOptions, TelemetryPayload, HandleErrorOptions };
