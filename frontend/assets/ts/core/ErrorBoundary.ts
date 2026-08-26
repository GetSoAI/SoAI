/* SoAI - Shared frontend error boundary [frontend/assets/ts/core/ErrorBoundary.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';

interface ErrorContext {
    operation?: string;
}

class ErrorBoundary {
    readonly moduleName: string;

    constructor(moduleName: string) {
        if (!moduleName.trim()) {
            throw new Error('ErrorBoundary requires a module name');
        }
        this.moduleName = moduleName.trim();
    }

    async execute<T>(functionValue: () => Promise<T> | T, context: string | ErrorContext | null = null): Promise<T> {
        if (!isFunction(functionValue)) {
            throw new Error('ErrorBoundary.execute requires a function');
        }
        try {
            return await functionValue();
        } catch (error) {
            const runtimeError = ensureError(error);
            this.handleError(runtimeError, context);
            throw runtimeError;
        }
    }

    wrap<T extends JsonValue[], R>(functionValue: (...inputArguments: T) => Promise<R> | R, context: string | ErrorContext | null = null): (...inputArguments: T) => Promise<R> {
        if (!isFunction(functionValue)) {
            throw new Error('ErrorBoundary.wrap requires a function');
        }
        return async (...inputArguments: T): Promise<R> => {
            try {
                return await functionValue(...inputArguments);
            } catch (error) {
                const runtimeError = ensureError(error);
                this.handleError(runtimeError, context);
                throw runtimeError;
            }
        };
    }

    handleError(error: Error | null, context: string | ErrorContext | null = null): void {
        if (isAbortError(error)) {
            return;
        }
        if (error && !claimErrorReporting(error)) {
            return;
        }
        const errorContext = isString(context) ? context : context?.operation || 'unknown';
        notifyHandledOperationError(error);

        errorHandler.error(this.moduleName, `Operation failed: ${errorContext}`, error);
    }

    async safeExecute<T>(functionValue: () => Promise<T> | T, context: string | ErrorContext | null = null): Promise<T> {
        return this.execute(functionValue, context);
    }
}

export { ErrorBoundary };
