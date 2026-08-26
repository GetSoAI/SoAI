/* SoAI - Shared frontend event bus [frontend/assets/ts/core/EventBus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString } from '@core/assertions.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

interface WaitForOptions<TDetail> {
    timeout?: number | null;
    filter?: ((detail: TDetail) => boolean) | null;
}

const normalizeEventName = (eventName: string): string => assertNonEmptyString(eventName, 'Event name');
const isEventHandler = (handler: EventListener | null | undefined): handler is EventListener => isFunction(handler);

const ensureHandler = (handler: EventListener): EventListener => {
    if (!isEventHandler(handler)) {
        throw new Error('Event handler must be a function');
    }
    return handler;
};

class EventBus extends EventTarget {
    emit(eventName: string): CustomEvent<null>;
    emit<TDetail>(eventName: string, detail: TDetail): CustomEvent<TDetail>;
    emit<TDetail>(eventName: string, detail: TDetail | null = null): CustomEvent<TDetail | null> {
        const normalizedEventName = normalizeEventName(eventName);
        const event = new CustomEvent(normalizedEventName, {
            detail,
            bubbles: false,
            cancelable: false
        });
        this.dispatchEvent(event);
        return event;
    }

    on(eventName: string, handler: EventListener, options: AddEventListenerOptions = {}): () => void {
        const normalizedEventName = normalizeEventName(eventName);
        const handlerFunctionValue = ensureHandler(handler);
        this.addEventListener(normalizedEventName, handlerFunctionValue, options);
        return () => this.removeEventListener(normalizedEventName, handlerFunctionValue, options);
    }

    once(eventName: string, handler: EventListener, options: AddEventListenerOptions = {}): () => void {
        const normalizedEventName = normalizeEventName(eventName);
        const handlerFunctionValue = ensureHandler(handler);
        const wrappedOptions = { ...options, once: true };
        this.addEventListener(normalizedEventName, handlerFunctionValue, wrappedOptions);
        return () => this.removeEventListener(normalizedEventName, handlerFunctionValue, wrappedOptions);
    }

    off(eventName: string, handler: EventListener, options: EventListenerOptions = {}): void {
        const normalizedEventName = normalizeEventName(eventName);
        const handlerFunctionValue = ensureHandler(handler);
        this.removeEventListener(normalizedEventName, handlerFunctionValue, options);
    }

    async waitFor<TDetail = null>(eventName: string, options: WaitForOptions<TDetail> = {}): Promise<TDetail> {
        const normalizedEventName = normalizeEventName(eventName);
        const { timeout = null, filter = null } = options;

        return await new Promise<TDetail>((resolve, reject) => {
            let timeoutId: ReturnType<typeof setTimeout> | null = null;
            let unsubscribe: (() => void) | null = null;

            const cleanup = (): void => {
                if (timeoutId !== null) {
                    clearTimeout(timeoutId);
                    timeoutId = null;
                }
                if (unsubscribe) {
                    unsubscribe();
                    unsubscribe = null;
                }
            };

            const handler = (event: Event): void => {
                if (!(event instanceof CustomEvent)) {
                    return;
                }
                const detail = event.detail;
                if (filter && !filter(detail)) {
                    return;
                }
                cleanup();
                resolve(detail);
            };

            unsubscribe = this.on(normalizedEventName, handler);

            if (timeout !== null && Number.isFinite(timeout) && timeout > 0) {
                timeoutId = setTimeout(() => {
                    cleanup();
                    reject(new Error(`Timeout waiting for event: ${String(eventName)}`));
                }, timeout);
            }
        });
    }
}

const EVENT_BUS_SERVICE_ID = 'core.eventBus';

const isEventBus = <T>(value: T): value is T & EventBus => {
    if (!isObject(value)) {
        return false;
    }
    return 'emit' in value && isFunction(value.emit) && 'on' in value && isFunction(value.on) && 'once' in value && isFunction(value.once) && 'off' in value && isFunction(value.off) && 'waitFor' in value && isFunction(value.waitFor);
};

const createEventBus = (): EventBus => new EventBus();

const getEventBus = (): EventBus => {
    const candidate = resolveKernelService(EVENT_BUS_SERVICE_ID);
    if (!isEventBus(candidate)) {
        throw new Error(`${EVENT_BUS_SERVICE_ID} is not registered`);
    }
    return candidate;
};

export { EventBus, createEventBus, getEventBus, EVENT_BUS_SERVICE_ID };
