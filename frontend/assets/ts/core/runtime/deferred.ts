/* SoAI - Shared runtime deferred [frontend/assets/ts/core/runtime/deferred.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

type DeferredRejectionReason = Error | JsonValue | undefined;

interface Deferred<T> {
    promise: Promise<T>;
    resolve: (value: T | PromiseLike<T>) => void;
    reject: (reason?: DeferredRejectionReason) => void;
}

const createDeferred = <T = void>(): Deferred<T> => {
    let resolve!: (value: T | PromiseLike<T>) => void;
    let reject!: (reason?: DeferredRejectionReason) => void;
    const promise = new Promise<T>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise;
        reject = rejectPromise;
    });
    return { promise, resolve, reject };
};

export { createDeferred };

export type { Deferred, DeferredRejectionReason };
