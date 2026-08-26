/* SoAI - Grouped DOM event binding lifecycle helper [frontend/assets/ts/core/dom/eventBindingGroup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isFunction } from '@core/typeGuards.ts';

interface EventBindingDefinition {
    target: EventTarget;
    type: string;
    listener: EventListener;
    options?: AddEventListenerOptions | boolean | undefined;
}

const isSignalAborted = (signal: AbortSignal | null | undefined): boolean => signal?.aborted === true;

const bindEventGroup = (definitions: readonly EventBindingDefinition[], signal?: AbortSignal | null): (() => void) => {
    if (isSignalAborted(signal)) {
        return (): void => {};
    }

    const bound: EventBindingDefinition[] = [];
    const cleanup = (): void => {
        signal?.removeEventListener('abort', cleanup);
        for (const definition of bound) {
            definition.target.removeEventListener(definition.type, definition.listener, definition.options);
        }
        bound.length = 0;
    };

    try {
        for (const definition of definitions) {
            if (!definition.type) {
                throw new Error('Event binding type is required');
            }
            if (!isFunction(definition.listener)) {
                throw new Error('Event binding listener must be a function');
            }
            definition.target.addEventListener(definition.type, definition.listener, definition.options);
            bound.push(definition);
        }
        signal?.addEventListener('abort', cleanup, { once: true });
        if (isSignalAborted(signal)) {
            cleanup();
        }
        return cleanup;
    } catch (error) {
        cleanup();
        throw ensureError(error);
    }
};

export { bindEventGroup };
export type { EventBindingDefinition };
