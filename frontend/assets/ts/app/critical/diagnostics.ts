/* SoAI - Frontend application diagnostics [frontend/assets/ts/app/critical/diagnostics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { telemetry } from '@core/telemetry/service.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isDefined, isFiniteNumber, isFunction, isObject, isString } from '@core/typeGuards.ts';

interface DiagnosticPayload {
    message?: string;
    detail?: ErrorDetail | PromiseRejectionDetail | null;
}

interface ErrorDetail extends JsonObject {
    filename: string | null;
    lineno: number | null;
    colno: number | null;
    stack: string | null;
}

interface PromiseRejectionDetail extends JsonObject {
    stack: string | null;
}

interface GlobalScopeWithEvents {
    addEventListener: (type: string, listener: (event: Event) => void, capture?: boolean) => void;
}

let diagnosticsInitialized = false;

const emitDiagnostic = (payload: DiagnosticPayload): void => {
    if (!payload || !isObject(payload)) {
        throw new Error('Diagnostics payload must be an object');
    }
    const payloadMessage = payload['message'];
    const payloadDetail = payload['detail'];
    const message = isString(payloadMessage) && payloadMessage ? payloadMessage : 'Unhandled error';
    const data = payloadDetail === undefined || payloadDetail === null ? null : payloadDetail;
    telemetry.emit({
        severity: 'error',
        module: 'Diagnostics',
        message,
        data,
        tags: ['browser', 'startup']
    });
};

const normalizeNullableString = (value: string | null | undefined): string | null => {
    return isString(value) && value ? value : null;
};

const normalizeNullableNumber = (value: number | null | undefined): number | null => {
    return isFiniteNumber(value) ? value : null;
};

const initializeDiagnostics = (): void => {
    if (diagnosticsInitialized) {
        return;
    }
    const scope: GlobalScopeWithEvents | null = isDefined(globalThis) ? globalThis : null;
    if (!scope || !isFunction(scope.addEventListener)) {
        throw new Error('Diagnostics initialization requires a browser scope');
    }
    diagnosticsInitialized = true;

    scope.addEventListener(
        'error',
        (event: Event) => {
            if (!(event instanceof ErrorEvent)) {
                return;
            }
            const error = event.error;
            const detail: ErrorDetail = {
                filename: normalizeNullableString(event.filename),
                lineno: normalizeNullableNumber(event.lineno),
                colno: normalizeNullableNumber(event.colno),
                stack: error instanceof Error ? normalizeNullableString(error.stack) : null
            };
            const hasContext = Object.values(detail).some((value) => value !== null);
            const message = normalizeNullableString(event.message);
            if (hasContext || message) {
                emitDiagnostic({
                    message: message || 'Unhandled error event',
                    detail
                });
            }
        },
        true
    );

    scope.addEventListener(
        'unhandledrejection',
        (event: Event) => {
            if (!(event instanceof PromiseRejectionEvent)) {
                return;
            }
            const runtimeError = ensureError(event.reason);
            const message = normalizeNullableString(runtimeError.message);
            const stack = normalizeNullableString(runtimeError.stack);
            if (message || stack) {
                emitDiagnostic({
                    message: message || 'Unhandled promise rejection',
                    detail: {
                        stack
                    }
                });
            }
        },
        true
    );
};

export { initializeDiagnostics };
