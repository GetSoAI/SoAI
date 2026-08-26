/* SoAI - Shared routing page streams [frontend/assets/ts/core/routing/pages/pageStreams.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import type { StreamHandle } from '@core/routing/pages/pagetypes/public.ts';
import { hasFunctionProperty, isRecordLike } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

type StreamHandleMethodName = 'abort' | 'cancel' | 'stop' | 'unsubscribe' | 'close';

interface StreamHandleMethods {
    abort?: () => void;
    cancel?: () => void;
    stop?: () => void;
    unsubscribe?: () => void;
    close?: () => void;
}

const hasStreamHandleMethod = <K extends StreamHandleMethodName>(candidate: StreamHandle | null | undefined, methodName: K): candidate is StreamHandleMethods & Record<K, () => void> => {
    if (!candidate || !isRecordLike(candidate)) {
        return false;
    }
    return hasFunctionProperty(candidate, methodName);
};

export class StreamHandleTracker {
    readonly prefix: string;
    readonly active: Map<string, StreamHandle>;

    constructor(point: string) {
        this.prefix = point;
        this.active = new Map();
    }

    get size(): number {
        return this.active.size;
    }

    has(key: string): boolean {
        return this.active.has(key);
    }

    track(key: string, streamHandle: StreamHandle): StreamHandle {
        this.active.set(key, streamHandle);
        return streamHandle;
    }

    release(key: string, options: { cancel?: boolean } = {}): void {
        const shouldCancel = options.cancel !== false;
        this.#stop(this.active.get(key), { cancel: shouldCancel });
        this.active.delete(key);
    }

    clear({ abort = true, cancel = true }: { abort?: boolean; cancel?: boolean } = {}): void {
        if (abort) {
            for (const streamHandle of this.active.values()) this.#stop(streamHandle, { cancel });
        }
        this.active.clear();
    }

    #stop(streamHandle: StreamHandle | undefined, options: { cancel: boolean }): void {
        if (!streamHandle) return;
        const call = (cleanup: () => void, method: string): boolean => {
            try {
                cleanup();
                return true;
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug('StreamPool', `Stream cleanup method ${method} failed`, runtimeError);
                throw ensureError(error);
            }
        };
        const methods: readonly StreamHandleMethodName[] = options.cancel ? ['abort', 'cancel', 'stop', 'unsubscribe', 'close'] : ['close', 'unsubscribe'];
        if (typeof streamHandle === 'object') {
            for (const match of methods) {
                if (hasStreamHandleMethod(streamHandle, match)) {
                    if (call(() => streamHandle[match](), match)) return;
                }
            }
        }
        if (typeof streamHandle === 'function' && options.cancel) {
            call(() => streamHandle(), 'direct');
        }
    }
}
