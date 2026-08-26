/* SoAI - Shared resource tracker actions [frontend/assets/ts/core/resourcetracker/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { Disposable, DisposableMetadata, DisposableResource } from '@core/resourcetracker/types.ts';

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

const clearTrackedTimers = (collections: TrackedTimerCollections): void => {
    collections.timeouts.forEach((timeoutId) => {
        const nativeHandle = collections.nativeTimeoutsById.get(timeoutId) ?? timeoutId;
        collections.clearTimeout(nativeHandle);
    });
    collections.timeouts.clear();
    collections.nativeTimeoutsById.clear();

    collections.intervals.forEach((intervalId) => {
        const nativeHandle = collections.nativeIntervalsById.get(intervalId) ?? intervalId;
        collections.clearInterval(nativeHandle);
    });
    collections.intervals.clear();
    collections.nativeIntervalsById.clear();

    collections.animationFrames.forEach((frameId) => collections.cancelAnimationFrame(frameId));
    collections.animationFrames.clear();
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

const cleanupTrackedDisposable = async (metadata: DisposableMetadata, onError: (error: Error) => void): Promise<void> => {
    try {
        if (isFunction(metadata.cleanup)) {
            await metadata.cleanup(metadata.disposable);
            return;
        }
        await invokeDisposable(metadata.disposable);
    } catch (error) {
        onError(ensureError(error));
    }
};

export { cleanupTrackedDisposable, clearTrackedTimers, invokeDisposable, safeDispose };
