/* SoAI - Page loading trail worker lifecycle [frontend/assets/ts/core/pageoutlet/spinner/SpinnerTrailRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getEventHub } from '@core/environment/public.ts';
import { readSpinnerTrailAppearance } from '@core/pageoutlet/spinner/appearance.ts';
import { decodeVisualizationResponse, type VisualizationRequest, type VisualizationResponse } from '@core/visualization/protocol.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { WorkerSession } from '@core/runtime/WorkerSession.ts';
import { secondsToMs } from '@core/time/durations.ts';
import { INTERFACE_SCALE_ATTRIBUTE } from '@core/layout/interfaceScale.ts';

class SpinnerTrailRenderer {
    readonly #spinner: HTMLElement;
    readonly #workerUrl: string;
    readonly #resources = new ResourceTracker();
    #worker: WorkerSession<VisualizationRequest, VisualizationResponse> | null = null;
    #canvas: HTMLCanvasElement | null = null;
    #state: 'idle' | 'starting' | 'ready' | 'unavailable' | 'disposed' = 'idle';
    #loading = false;

    constructor(spinner: HTMLElement, workerUrl: string) {
        this.#spinner = spinner;
        this.#workerUrl = workerUrl;
        const view = spinner.ownerDocument.defaultView;
        if (view?.ResizeObserver) {
            const observer = new view.ResizeObserver(this.#refresh);
            observer.observe(spinner);
            this.#resources.track(observer);
        }
        if (view?.MutationObserver) {
            const observer = new view.MutationObserver(this.#refresh);
            observer.observe(spinner.ownerDocument.documentElement, { attributes: true, attributeFilter: ['class', 'style', INTERFACE_SCALE_ATTRIBUTE] });
            this.#resources.track(observer);
        }
        this.#resources.addEventListener(getEventHub(), 'themeChanged', this.#refresh);
        this.#resources.addEventListener(spinner.ownerDocument, 'visibilitychange', this.#refresh);
        if (view) this.#resources.addEventListener(view, 'resize', this.#refresh);
    }

    setLoading(loading: boolean): void {
        if (loading === this.#loading) return;
        this.#loading = loading;
        this.#refresh();
    }

    #refresh = (): void => {
        if (this.#state === 'unavailable' || this.#state === 'disposed') return;
        try {
            if (!this.#loading || this.#spinner.ownerDocument.visibilityState === 'hidden') {
                this.#worker?.postMessage({ type: 'suspend' });
                return;
            }
            const appearance = readSpinnerTrailAppearance(this.#spinner, this.#canvas);
            if (this.#worker) {
                this.#worker.postMessage({ type: 'renderSpinner', appearance });
                return;
            }
            const view = this.#spinner.ownerDocument.defaultView;
            const canvas = this.#spinner.ownerDocument.createElement('canvas');
            if (!view?.Worker || typeof canvas.transferControlToOffscreen !== 'function') {
                this.#state = 'unavailable';
                this.#resources.cleanup();
                return;
            }
            canvas.className = 'page-outlet-spinner-trail';
            canvas.setAttribute('aria-hidden', 'true');
            this.#spinner.append(canvas);
            this.#canvas = canvas;
            const offscreen = canvas.transferControlToOffscreen();
            const worker = new WorkerSession<VisualizationRequest, VisualizationResponse>({
                createWorker: () => new view.Worker(this.#workerUrl, { type: 'module', name: 'soai-loading-animation' }),
                label: 'Loading animation worker',
                timeoutMs: secondsToMs(3),
                decode: decodeVisualizationResponse,
                isReady: (response) => response.type === 'ready',
                onMessage: (response) => {
                    if (response.type !== 'unavailable') throw new Error('Loading animation worker returned an unexpected response');
                    this.#fail(new Error(response.reason));
                },
                onFailure: (error) => this.#fail(error)
            });
            this.#worker = worker;
            this.#state = 'starting';
            void worker.ready
                .then(() => {
                    if (this.#worker !== worker || this.#state !== 'starting') return;
                    this.#state = 'ready';
                    this.#spinner.dataset['spinnerRenderer'] = 'gpu';
                    this.#refresh();
                })
                .catch((error) => this.#fail(ensureError(error)));
            worker.postMessage({ type: 'initializeSpinner', canvas: offscreen, appearance }, [offscreen]);
        } catch (error) {
            this.#fail(ensureError(error));
        }
    };

    #releaseWorker(): void {
        const worker = this.#worker;
        this.#worker = null;
        worker?.dispose();
        this.#canvas?.remove();
        this.#canvas = null;
        delete this.#spinner.dataset['spinnerRenderer'];
    }

    #fail(error: Error): void {
        if (this.#state === 'unavailable' || this.#state === 'disposed') return;
        this.#state = 'unavailable';
        this.#releaseWorker();
        this.#resources.cleanup();
        errorHandler.warn('PageOutlet', 'GPU loading animation unavailable; retaining the CSS loading animation', error);
    }

    dispose(): void {
        if (this.#state === 'disposed') return;
        this.#state = 'disposed';
        this.#releaseWorker();
        this.#resources.cleanup();
    }
}

export { SpinnerTrailRenderer };
