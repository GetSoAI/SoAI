/* SoAI - Chart domain event ownership [frontend/assets/ts/features/charts/session/ChartEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import { CHART_EVENT_NAMES } from '@features/charts/component/chartComponentStatics.ts';
import type { ChartEventDetail } from '@features/charts/component/effects.ts';
import type { EventHandler } from '@features/charts/component/chartComponentTypes.ts';

class ChartEvents {
    readonly #element: HTMLElement;
    readonly #handlers = new Map<string, EventHandler[]>();
    #destroyed = false;

    constructor(element: HTMLElement) {
        this.#element = element;
    }

    on(event: string, handler: EventHandler | null): () => void {
        if (this.#destroyed) throw new Error('Cannot subscribe to destroyed chart events');
        if (!CHART_EVENT_NAMES.has(event)) throw new Error(`Unsupported chart event: ${event}`);
        if (!isFunction(handler)) throw new TypeError('Chart event handler must be a function');
        const handlers = this.#handlers.get(event) ?? [];
        this.#handlers.set(event, [...handlers, handler]);
        return () => this.off(event, handler);
    }

    off(event: string, handler?: EventHandler): void {
        if (!CHART_EVENT_NAMES.has(event)) throw new Error(`Unsupported chart event: ${event}`);
        if (!handler) {
            this.#handlers.delete(event);
            return;
        }
        const handlers = this.#handlers.get(event);
        if (!handlers) return;
        const remaining = handlers.filter((candidate) => candidate !== handler);
        if (remaining.length > 0) this.#handlers.set(event, remaining);
        else this.#handlers.delete(event);
    }

    emit(event: string, detail?: ChartEventDetail): void {
        if (this.#destroyed) throw new Error('Cannot emit from destroyed chart events');
        if (!CHART_EVENT_NAMES.has(event)) throw new Error(`Unsupported chart event: ${event}`);
        for (const handler of this.#handlers.get(event) ?? []) handler(detail);
        this.#element.dispatchEvent(new CustomEvent(event, { detail, bubbles: true, cancelable: true }));
    }

    clear(): void {
        this.#handlers.clear();
    }

    initialize(signal: AbortSignal): void {
        signal.throwIfAborted();
    }

    destroy(): void {
        this.clear();
        this.#destroyed = true;
    }
}

export { ChartEvents };
