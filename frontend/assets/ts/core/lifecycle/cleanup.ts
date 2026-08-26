/* SoAI - Shared lifecycle cleanup [frontend/assets/ts/core/lifecycle/cleanup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isThenable } from '@core/typeGuards.ts';

type Cleanup = () => void | Promise<void>;
type CleanupErrorHandler = (error: Error) => void;

const runCleanup = (cleanup: Cleanup | null | undefined, onError: CleanupErrorHandler): void => {
    if (!cleanup) {
        return;
    }
    try {
        const result = cleanup();
        if (isThenable(result)) {
            void Promise.resolve(result).catch((error) => {
                onError(ensureError(error));
            });
        }
    } catch (error) {
        onError(ensureError(error));
    }
};

const drainCleanupStack = (cleanups: Cleanup[], onError: CleanupErrorHandler): void => {
    while (cleanups.length > 0) {
        runCleanup(cleanups.pop(), onError);
    }
};

const runCleanupCallbacks = (cleanups: readonly Cleanup[], onError: CleanupErrorHandler): void => {
    for (const cleanup of cleanups) {
        runCleanup(cleanup, onError);
    }
};

const runCleanupStepCollectingFailure = (cleanup: () => void, failures: Error[]): void => {
    try {
        cleanup();
    } catch (error) {
        failures.push(ensureError(error));
    }
};

const runAsyncCleanupStepCollectingFailure = async (cleanup: () => Promise<void>, failures: Error[]): Promise<void> => {
    try {
        await cleanup();
    } catch (error) {
        failures.push(ensureError(error));
    }
};

const throwCollectedCleanupFailures = (failures: readonly Error[]): void => {
    if (failures.length === 0) {
        return;
    }
    if (failures.length === 1) {
        const firstFailure = failures[0] ?? null;
        if (firstFailure !== null) {
            throw firstFailure;
        }
    }
    throw new AggregateError(failures, 'Cleanup failed');
};

export { drainCleanupStack, runAsyncCleanupStepCollectingFailure, runCleanup, runCleanupCallbacks, runCleanupStepCollectingFailure, throwCollectedCleanupFailures };
export type { Cleanup, CleanupErrorHandler };
