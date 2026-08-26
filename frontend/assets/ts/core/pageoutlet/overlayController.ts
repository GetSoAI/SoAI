/* SoAI - Shared page outlet overlay controller [frontend/assets/ts/core/pageoutlet/overlayController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { applyPageOutletErrorState } from '@core/pageoutlet/actions.ts';
import { createOverlayElements, setPageOutletState } from '@core/pageoutlet/dom.ts';
import type { PageOutletOverlayElements, PageOutletRetryHandler, PageOutletStateOptions } from '@core/pageoutlet/types.ts';
import { isFunction } from '@core/typeGuards.ts';

class PageOutletOverlayController {
    #resources: ResourceTracker;
    #container: HTMLElement | null = null;
    #overlayElements: PageOutletOverlayElements | null = null;
    #retryHandler: PageOutletRetryHandler | null = null;
    #state: string = 'idle';
    #clearSkeleton: () => void;

    constructor(options: { resources: ResourceTracker; clearSkeleton: () => void }) {
        this.#resources = options.resources;
        this.#clearSkeleton = options.clearSkeleton;
    }

    setRetryHandler(handler: PageOutletRetryHandler | null): void {
        this.#retryHandler = isFunction(handler) ? handler : null;
    }

    setContainer(container: HTMLElement): void {
        this.#container = container;
        this.#ensureOverlay();
    }

    getState(): string {
        return this.#state;
    }

    applyErrorState(error: Error): void {
        applyPageOutletErrorState(error, (state, options) => this.setState(state, options));
    }

    setState(state: string, { label = null, detail = null, delayed = false }: PageOutletStateOptions = {}): void {
        const container = this.#requireContainer();
        this.#state = state;
        const overlayElements = this.#overlayElements;
        const resolvedOverlay = setPageOutletState({
            state,
            label,
            detail,
            delayed,
            container,
            overlayElements,
            ensureOverlay: () => this.#ensureOverlay(),
            clearSkeleton: () => this.#clearSkeleton(),
            hasRetryHandler: isFunction(this.#retryHandler)
        });
        if (resolvedOverlay) {
            this.#overlayElements = resolvedOverlay;
        }
    }

    #ensureOverlay(): PageOutletOverlayElements {
        const container = this.#requireContainer();
        const existing = this.#overlayElements;
        if (existing && existing.overlay.isConnected && existing.overlay.parentElement === container) {
            return existing;
        }
        const overlayElements: PageOutletOverlayElements = createOverlayElements(container, (button: HTMLButtonElement): void => {
            this.#resources.addEventListener(button, 'click', () => {
                const handler = this.#retryHandler;
                if (isFunction(handler)) {
                    handler();
                }
            });
        });
        this.#overlayElements = overlayElements;
        return overlayElements;
    }

    #requireContainer(): HTMLElement {
        if (!this.#container) {
            throw new Error('PageOutlet requires a container before creating the overlay');
        }
        return this.#container;
    }
}

export { PageOutletOverlayController };
