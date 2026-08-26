/* SoAI - Shared realtime resource snapshot wait [frontend/assets/ts/core/realtime/resourceSnapshotWait.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isObject } from '@core/typeGuards.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';

interface ResourceSnapshotWaitHost<T> {
    getResource(resourceName: string): JsonValue | ResourceSnapshot | null | undefined;
    subscribe(resourceName: string, listener: (snapshot: JsonValue | ResourceSnapshot | null | undefined) => void, options: { immediate: true; ensureStart: true }): () => void;
    extract(raw: JsonValue | null | undefined): T | null;
}

const unwrapResourceSnapshotValue = (snapshot: JsonValue | ResourceSnapshot | null | undefined): JsonValue | null | undefined => {
    if (isObject(snapshot) && hasOwn(snapshot, 'value')) {
        const value = snapshot['value'];
        return isJsonValue(value) ? value : null;
    }
    return isJsonValue(snapshot) ? snapshot : null;
};

const waitForResourceSnapshot = async <T>(inputArguments: { host: ResourceSnapshotWaitHost<T>; resourceName: string; timeoutMs: number; timeoutMessage: string; logContext: string; logMetadata?: Record<string, JsonValue | null | undefined> | undefined }): Promise<T> => {
    const direct = inputArguments.host.extract(unwrapResourceSnapshotValue(inputArguments.host.getResource(inputArguments.resourceName)));
    if (direct !== null) {
        return direct;
    }

    const startedAtMs = Date.now();
    const deferred = createDeferred<T>();
    let finished = false;
    let unsubscribe: (() => void) | null = null;
    const cleanup = (): void => {
        if (finished) {
            return;
        }
        finished = true;
        if (unsubscribe === null) {
            return;
        }
        try {
            unsubscribe();
        } catch (error) {
            errorHandler.debug(inputArguments.logContext, 'Resource snapshot unsubscribe failed', ensureError(error));
        }
    };

    const assignedUnsubscribe = inputArguments.host.subscribe(
        inputArguments.resourceName,
        (snapshot: JsonValue | ResourceSnapshot | null | undefined): void => {
            if (finished) {
                return;
            }
            let match: T | null;
            try {
                match = inputArguments.host.extract(unwrapResourceSnapshotValue(snapshot));
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug(inputArguments.logContext, 'Resource snapshot extraction failed', runtimeError);
                cleanup();
                deferred.reject(runtimeError);
                return;
            }
            if (match === null) {
                return;
            }
            errorHandler.debug(inputArguments.logContext, 'Resource snapshot resolved via subscription', {
                ...(inputArguments.logMetadata ?? {}),
                elapsedMs: Date.now() - startedAtMs
            });
            cleanup();
            deferred.resolve(match);
        },
        { immediate: true, ensureStart: true }
    );
    unsubscribe = assignedUnsubscribe;
    if (finished) {
        try {
            assignedUnsubscribe();
        } catch (error) {
            errorHandler.debug(inputArguments.logContext, 'Resource snapshot unsubscribe failed', ensureError(error));
        }
    }

    try {
        return await withTimeout(deferred.promise, {
            timeoutMs: inputArguments.timeoutMs,
            timeoutMessage: inputArguments.timeoutMessage
        });
    } finally {
        cleanup();
    }
};

export { unwrapResourceSnapshotValue, waitForResourceSnapshot };
export type { ResourceSnapshotWaitHost };
