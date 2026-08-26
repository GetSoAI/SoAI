/* SoAI - Shared frontend detached context [frontend/assets/ts/core/detachedContext.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import type { PageHost } from '@core/pagehost/service.ts';
import type { PageInstance } from '@core/pagehost/types.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

type ContextListener<T> = (value: T | null) => void;

interface DetachedContextInstance<T> {
    get: () => T | null;
    set: (value: T | null) => T | null;
    clear: () => void;
    subscribe: (listener: ContextListener<T>) => () => boolean;
}

interface DetachedWindowContext {
    pageId: string;
    windowId: string;
    parameters: JsonObject;
    host: PageHost | null;
    instance: PageInstance | null;
    stage: string;
}

const createDetachedContext = <T>(): DetachedContextInstance<T> => {
    let currentValue: T | null = null;
    const listeners = new Set<ContextListener<T>>();
    const publish = (value: T | null): void => {
        listeners.forEach((listener) => {
            try {
                listener(value);
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('Detached', 'Context subscriber failed', runtimeError);
            }
        });
    };
    return Object.freeze({
        get(): T | null {
            return currentValue;
        },
        set(value: T | null): T | null {
            currentValue = value ?? null;
            publish(currentValue);
            return currentValue;
        },
        clear(): void {
            currentValue = null;
            publish(currentValue);
        },
        subscribe(listener: ContextListener<T>): () => boolean {
            if (!isFunction(listener)) {
                return () => false;
            }
            listeners.add(listener);
            return () => listeners.delete(listener);
        }
    });
};

const detachedWindowContextRegistry = new Map<string, DetachedContextInstance<DetachedWindowContext>>();

const getDetachedWindowContextForWindow = (windowId: string): DetachedContextInstance<DetachedWindowContext> => {
    if (!detachedWindowContextRegistry.has(windowId)) {
        detachedWindowContextRegistry.set(windowId, createDetachedContext<DetachedWindowContext>());
    }
    const context = detachedWindowContextRegistry.get(windowId);
    if (!context) {
        throw new Error('Detached window context must be available');
    }
    return context;
};

const clearDetachedWindowContextForWindow = (windowId: string): void => {
    const context = detachedWindowContextRegistry.get(windowId);
    if (context) {
        context.clear();
        detachedWindowContextRegistry.delete(windowId);
    }
};

export { createDetachedContext, getDetachedWindowContextForWindow, clearDetachedWindowContextForWindow };

export type { ContextListener, DetachedContextInstance, DetachedWindowContext };
