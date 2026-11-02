/* SoAI - Shared page outlet overlay controller [frontend/assets/ts/core/pageoutlet/overlayController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolve } from '@core/dom/dom.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { applyPageOutletErrorState } from '@core/pageoutlet/actions.ts';
import { createOverlayElements, setPageOutletState } from '@core/pageoutlet/dom.ts';
import type { PageOutletOverlayElements, PageOutletRetryHandler, PageOutletStateOptions } from '@core/pageoutlet/types.ts';
import { isFunction, isHTMLElement, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { SpinnerTrailRenderer } from '@core/pageoutlet/spinner/SpinnerTrailRenderer.ts';

class PageOutletOverlayController {
    #resources: ResourceTracker;
    #container: HTMLElement | null = null;
    #overlayElements: PageOutletOverlayElements | null = null;
    #retryHandler: PageOutletRetryHandler | null = null;
    #state: string = 'idle';
    #settledState: { state: string; options: PageOutletStateOptions } = { state: 'idle', options: {} };
    #spinnerWorkerUrl: string | undefined;
    #spinnerRenderer: SpinnerTrailRenderer | null = null;
    readonly #onStateChanged: (() => void) | undefined;

    constructor(options: { resources: ResourceTracker; spinnerWorkerUrl?: string | undefined; onStateChanged?: (() => void) | undefined }) {
        this.#resources = options.resources;
        this.#spinnerWorkerUrl = options.spinnerWorkerUrl;
        this.#onStateChanged = options.onStateChanged;
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

    setSkeleton(route: string): void {
        if (!isString(route) || !route.trim()) throw new Error('PageOutlet skeleton requires a route identifier');
        this.#requireContainer().dataset['routeSkeleton'] = route.trim();
        this.setState('loading', { label: i18n.t('pageOutlet.loading') });
    }

    applyErrorState(error: Error): void {
        applyPageOutletErrorState(error, (state, options) => this.setState(state, options));
    }

    restoreSettledState(): void {
        const { state, options } = this.#settledState;
        this.setState(state, options);
    }

    setState(state: string, { label = null, detail = null, delayed = false }: PageOutletStateOptions = {}): void {
        const container = this.#requireContainer();
        this.#state = state;
        if (state !== 'loading') this.#settledState = { state, options: { label, detail, delayed } };
        const overlayElements = this.#overlayElements;
        const resolvedOverlay = setPageOutletState({
            state,
            label,
            detail,
            delayed,
            container,
            overlayElements,
            ensureOverlay: () => this.#ensureOverlay(),
            hasRetryHandler: isFunction(this.#retryHandler)
        });
        if (resolvedOverlay) {
            this.#overlayElements = resolvedOverlay;
        }
        this.#spinnerRenderer?.setLoading(state === 'loading');
        this.#onStateChanged?.();
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
        if (this.#spinnerRenderer) {
            this.#spinnerRenderer.dispose();
            this.#resources.untrack(this.#spinnerRenderer);
            this.#spinnerRenderer = null;
        }
        if (this.#spinnerWorkerUrl) {
            const spinner = resolve('.page-outlet-overlay-spinner', overlayElements.overlay);
            if (!isHTMLElement(spinner)) throw new Error('Page outlet loading spinner is required');
            this.#spinnerRenderer = this.#resources.track(new SpinnerTrailRenderer(spinner, this.#spinnerWorkerUrl));
        }
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
