/* SoAI - Bounded async scheduling for worker requests [frontend/assets/ts/features/chat/messagerenderworker/boundedRequestScheduler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';

type TaskFactory<TResult> = () => Promise<TResult>;

type RunBoundedRequestsArguments<TResult> = {
    factories: readonly TaskFactory<TResult>[];
    maxInFlight: number;
    signal: AbortSignal | null;
    stopOnError?: boolean;
    onError?: (error: Error) => void;
};

const runBoundedRequests = async <TResult>(inputArguments: RunBoundedRequestsArguments<TResult>): Promise<TResult[]> => {
    if (!Number.isInteger(inputArguments.maxInFlight) || inputArguments.maxInFlight <= 0) {
        throw new Error('Worker request scheduler requires a positive maxInFlight');
    }

    const stopOnError = inputArguments.stopOnError !== false;
    if (!stopOnError && typeof inputArguments.onError !== 'function') {
        throw new Error('Worker request scheduler requires onError when stopOnError is false');
    }

    const results: TResult[] = [];
    const inFlight = new Set<Promise<void>>();
    let nextIndex = 0;
    let firstError: Error | null = null;
    const wasAborted = (): boolean => inputArguments.signal?.aborted === true;

    const scheduleNext = (): void => {
        if (wasAborted()) {
            return;
        }
        if (firstError) {
            return;
        }
        if (nextIndex >= inputArguments.factories.length) {
            return;
        }
        const factory = inputArguments.factories[nextIndex];
        nextIndex += 1;
        if (!factory) {
            throw new Error('Worker request scheduler missing factory');
        }
        const promise = factory()
            .then((value) => {
                if (!wasAborted()) {
                    results.push(value);
                }
            })
            .catch((error) => {
                if (wasAborted()) {
                    return;
                }
                const normalized = ensureError(error);
                if (!stopOnError) {
                    inputArguments.onError?.(normalized);
                    return;
                }
                if (!firstError) {
                    firstError = normalized;
                }
            });
        const wrapped = promise.finally(() => {
            inFlight.delete(wrapped);
        });
        inFlight.add(wrapped);
    };

    while (nextIndex < inputArguments.factories.length) {
        if (wasAborted()) {
            break;
        }
        if (firstError) {
            break;
        }
        while (inFlight.size < inputArguments.maxInFlight && nextIndex < inputArguments.factories.length) {
            scheduleNext();
            if (firstError) {
                break;
            }
        }
        if (inFlight.size === 0) {
            break;
        }
        await Promise.race(inFlight);
    }

    if (wasAborted()) {
        return results;
    }

    if (inFlight.size > 0) {
        await Promise.all(inFlight);
    }

    if (firstError) {
        throw firstError;
    }
    return results;
};

export { runBoundedRequests };
export type { RunBoundedRequestsArguments, TaskFactory };
