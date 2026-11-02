/* SoAI - Shared resource tracker actions [frontend/assets/ts/core/resourcetracker/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { Disposable, DisposableMetadata, DisposableResource, EventListenerMetadata } from '@core/resourcetracker/types.ts';
import { createDeferred } from '@core/runtime/deferred.ts';

type NativeTimerHandle = number | ReturnType<typeof setTimeout>;

interface TrackedTimerCollections {
    timeouts: Set<number>;
    intervals: Set<number>;
    animationFrames: Set<number>;
    nativeTimeoutsById: Map<number, NativeTimerHandle>;
    nativeIntervalsById: Map<number, NativeTimerHandle>;
    clearTimeout: (handle: NativeTimerHandle) => void;
    clearInterval: (handle: NativeTimerHandle) => void;
    cancelAnimationFrame: (frameId: number) => void;
}

const clearTrackedTimers = (collections: TrackedTimerCollections): Error[] => {
    const failures: Error[] = [];
    const clearTimers = (timers: Set<number>, nativeHandles: Map<number, NativeTimerHandle>, release: (handle: NativeTimerHandle) => void): void => {
        for (const timerId of [...timers]) {
            try {
                release(nativeHandles.get(timerId) ?? timerId);
                timers.delete(timerId);
                nativeHandles.delete(timerId);
            } catch (error) {
                failures.push(ensureError(error));
            }
        }
    };
    clearTimers(collections.timeouts, collections.nativeTimeoutsById, collections.clearTimeout);
    clearTimers(collections.intervals, collections.nativeIntervalsById, collections.clearInterval);
    for (const frameId of [...collections.animationFrames]) {
        try {
            collections.cancelAnimationFrame(frameId);
            collections.animationFrames.delete(frameId);
        } catch (error) {
            failures.push(ensureError(error));
        }
    }
    return failures;
};

const clearTrackedEventListeners = (listeners: Set<EventListenerMetadata>, onError: (error: Error) => void): Error[] => {
    const failures: Error[] = [];
    for (const metadata of [...listeners]) {
        try {
            metadata.element.removeEventListener?.(metadata.event, metadata.handler, metadata.options);
            listeners.delete(metadata);
        } catch (error) {
            const failure = ensureError(error);
            failures.push(failure);
            onError(failure);
        }
    }
    return failures;
};

const settleTrackedDisposables = async (disposables: Set<DisposableMetadata>, release: (metadata: DisposableMetadata) => Promise<Error | null>, drain: boolean): Promise<Error[]> => {
    const attempted = new Set<DisposableMetadata>();
    const failures: Error[] = [];
    do {
        const pending = [...disposables].filter((metadata) => !attempted.has(metadata));
        if (pending.length === 0) break;
        for (const metadata of pending) attempted.add(metadata);
        const outcomes = await Promise.all(pending.map(release));
        for (const outcome of outcomes) if (outcome) failures.push(outcome);
    } while (drain);
    return failures;
};

const safeDispose = async (resource: DisposableResource): Promise<void> => {
    if (typeof resource !== 'object' || resource === null) {
        return;
    }

    const disposable: Disposable = resource;
    if (isFunction(disposable.destroy)) {
        await disposable.destroy();
        return;
    }
    if (isFunction(disposable.dispose)) {
        await disposable.dispose();
        return;
    }
    if (isFunction(disposable.cleanup)) {
        await disposable.cleanup();
        return;
    }
    if (isFunction(disposable.close)) {
        await disposable.close();
        return;
    }
    if (isFunction(disposable.abort)) {
        await disposable.abort();
        return;
    }
    if (isFunction(disposable.cancel)) {
        await disposable.cancel();
        return;
    }
    if (isFunction(disposable.disconnect)) {
        await disposable.disconnect();
        return;
    }
    if (isFunction(disposable.stop)) {
        await disposable.stop();
        return;
    }
    if (isFunction(disposable.clear)) {
        await disposable.clear();
        return;
    }
    if (isFunction(disposable.unsubscribe)) {
        await disposable.unsubscribe();
        return;
    }
    if (isFunction(disposable.off)) {
        await disposable.off();
    }
};

const invokeDisposable = async (disposable: DisposableResource): Promise<void> => {
    if (!disposable) {
        return;
    }

    if (isFunction(disposable)) {
        await disposable();
        return;
    }

    await safeDispose(disposable);
};

const cleanupTrackedDisposable = (metadata: DisposableMetadata, onError: (error: Error) => void): Promise<Error | null> => {
    if (metadata.completion) return metadata.completion;
    const completion = createDeferred<Error | null>();
    metadata.completion = completion.promise;
    const release = async (): Promise<Error | null> => {
        try {
            if (isFunction(metadata.cleanup)) {
                await metadata.cleanup(metadata.disposable);
            } else {
                await invokeDisposable(metadata.disposable);
            }
            return null;
        } catch (error) {
            const failure = ensureError(error);
            onError(failure);
            return failure;
        }
    };
    void release().then(completion.resolve, (error) => completion.resolve(ensureError(error)));
    return completion.promise;
};

export { cleanupTrackedDisposable, clearTrackedEventListeners, clearTrackedTimers, invokeDisposable, safeDispose, settleTrackedDisposables };
