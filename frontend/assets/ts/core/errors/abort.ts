/* SoAI - Abort error normalization helpers [frontend/assets/ts/core/errors/abort.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type AbortErrorFieldPrimitive = string | number | boolean | bigint | symbol | null | undefined | void;

interface AbortErrorFieldRecord {
    readonly [key: string]: AbortErrorFieldValue;
}

type AbortErrorFieldValue = AbortErrorFieldPrimitive | Error | AbortErrorFieldRecord | readonly AbortErrorFieldValue[];

const RE_ABORT_TEXT = /^(aborterror|operation aborted\.?|request aborted\.?|aborted\.?|the operation was aborted\.?)$/i;
const DOM_EXCEPTION_CONSTRUCTOR = typeof globalThis.DOMException === 'function' ? globalThis.DOMException : null;

const createAbortError = (message = 'Operation aborted'): Error => {
    const error = new Error(message);
    error.name = 'AbortError';
    return error;
};

const throwIfAborted = (signal: AbortSignal | null | undefined, message = 'Operation aborted'): void => {
    if (signal?.aborted) {
        throw createAbortError(message);
    }
};

interface AbortSignalScope {
    signal: AbortSignal;
    cleanup: () => void;
}

const createAbortSignalScope = (signals: readonly (AbortSignal | null | undefined)[]): AbortSignalScope => {
    const activeSignals = signals.filter((signal): signal is AbortSignal => signal !== null && signal !== undefined);
    if (activeSignals.length === 0) {
        const controller = new AbortController();
        return { signal: controller.signal, cleanup: () => {} };
    }
    if (activeSignals.length === 1) {
        const activeSignal = activeSignals[0];
        if (activeSignal === undefined) {
            throw new Error('Abort signal scope lost its active signal');
        }
        return { signal: activeSignal, cleanup: () => {} };
    }
    const controller = new AbortController();
    const abort = (): void => {
        controller.abort();
    };
    const cleanup = (): void => {
        activeSignals.forEach((signal) => signal.removeEventListener('abort', abort));
        controller.signal.removeEventListener('abort', cleanup);
    };
    if (activeSignals.some((signal) => signal.aborted)) {
        controller.abort();
        return { signal: controller.signal, cleanup: () => {} };
    }
    activeSignals.forEach((signal) => signal.addEventListener('abort', abort, { once: true }));
    controller.signal.addEventListener('abort', cleanup, { once: true });
    return { signal: controller.signal, cleanup };
};

const raceWithAbortSignal = <T>(task: Promise<T>, signal: AbortSignal): Promise<T> => {
    if (signal.aborted) {
        return Promise.reject(createAbortError());
    }
    return new Promise<T>((resolve, reject) => {
        let settled = false;
        const cleanup = (): void => signal.removeEventListener('abort', onAbort);
        const onAbort = (): void => {
            if (settled) return;
            settled = true;
            cleanup();
            reject(createAbortError());
        };
        signal.addEventListener('abort', onAbort, { once: true });
        task.then(
            (value) => {
                if (settled) return;
                settled = true;
                cleanup();
                resolve(value);
            },
            (error) => {
                if (settled) return;
                settled = true;
                cleanup();
                reject(error);
            }
        );
    });
};

const runWithAbortSignalScope = async <T>(signals: readonly (AbortSignal | null | undefined)[], operation: (signal: AbortSignal) => Promise<T>): Promise<T> => {
    const scope = createAbortSignalScope(signals);
    try {
        return await operation(scope.signal);
    } finally {
        scope.cleanup();
    }
};

const isAbortFieldRecord = <T>(value: T): value is T & AbortErrorFieldRecord => {
    if (value === null || value === undefined) {
        return false;
    }
    return typeof value === 'object' || typeof value === 'function';
};

const readAbortErrorField = <T>(value: T, key: string): AbortErrorFieldValue => {
    if (!isAbortFieldRecord(value)) {
        return undefined;
    }
    return value[key];
};

const isAbortText = <T>(value: T): boolean => {
    return typeof value === 'string' && RE_ABORT_TEXT.test(value.trim());
};

const isAbortError = <T>(error: T): boolean => {
    if (error === null || error === undefined) return false;
    if (typeof error === 'string') return isAbortText(error);
    if (DOM_EXCEPTION_CONSTRUCTOR !== null && error instanceof DOM_EXCEPTION_CONSTRUCTOR && error.name === 'AbortError') return true;
    if (error instanceof Error && error.name === 'AbortError') return true;
    if (!isAbortFieldRecord(error)) return false;
    const nameValue = readAbortErrorField(error, 'name');
    if (typeof nameValue === 'string' && nameValue === 'AbortError') return true;
    const codeValue = readAbortErrorField(error, 'code');
    if (codeValue === 20) return true;
    return isAbortText(readAbortErrorField(error, 'message')) || isAbortText(readAbortErrorField(error, 'reason'));
};

export { createAbortError, createAbortSignalScope, isAbortError, raceWithAbortSignal, runWithAbortSignalScope, throwIfAborted };
export type { AbortSignalScope };
