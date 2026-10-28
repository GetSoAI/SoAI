/* SoAI - Isolated offscreen visualization execution [frontend/assets/ts/core/visualization/VisualizationRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SpinnerGpuTrail } from '@core/visualization/spinnerGpuTrail.ts';
import { isVisualizationRequest, type VisualizationRequest, type VisualizationResponse } from '@core/visualization/protocol.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface VisualizationRuntimeDependencies {
    post: (response: VisualizationResponse) => void;
    requestFrame: (callback: FrameRequestCallback) => number;
    cancelFrame: (identifier: number) => void;
    now: () => number;
}

class VisualizationRuntime {
    readonly #dependencies: VisualizationRuntimeDependencies;
    #spinner: SpinnerGpuTrail | null = null;
    #animationFrame: number | null = null;
    #startedAt = 0;
    #closed = false;

    constructor(dependencies: VisualizationRuntimeDependencies) {
        this.#dependencies = dependencies;
    }

    receive(request: VisualizationRequest | null): void {
        if (this.#closed) return;
        try {
            if (!isVisualizationRequest(request)) throw new Error('Visualization worker received an invalid request');
            if (request.type === 'suspend') {
                this.#suspend();
                return;
            }
            if (request.type === 'initializeSpinner') {
                if (this.#spinner) throw new Error('Visualization worker is already initialized');
                this.#spinner = new SpinnerGpuTrail(request.canvas);
                this.#startedAt = this.#dependencies.now();
                this.#spinner.configure(request.appearance);
                this.#drawSpinner();
                if (!this.#closed) this.#dependencies.post({ type: 'ready' });
                return;
            }
            if (!this.#spinner) throw new Error('Loading visualization is not initialized');
            this.#spinner.configure(request.appearance);
            if (this.#animationFrame === null) this.#drawSpinner();
        } catch (error) {
            this.#fail(ensureError(error));
        }
    }

    #drawSpinner = (): void => {
        this.#animationFrame = null;
        if (this.#closed) return;
        try {
            if (!this.#spinner) throw new Error('Loading visualization is not initialized');
            this.#spinner.draw(this.#dependencies.now() - this.#startedAt);
            this.#animationFrame = this.#dependencies.requestFrame(this.#drawSpinner);
        } catch (error) {
            this.#fail(ensureError(error));
        }
    };

    #suspend(): void {
        if (this.#animationFrame !== null) this.#dependencies.cancelFrame(this.#animationFrame);
        this.#animationFrame = null;
    }

    #fail(error: Error): void {
        if (this.#closed) return;
        this.dispose();
        this.#dependencies.post({ type: 'unavailable', reason: error.message });
    }

    dispose(): void {
        this.#closed = true;
        this.#suspend();
        this.#spinner?.dispose();
        this.#spinner = null;
    }
}

export { VisualizationRuntime };
