/* SoAI - Chart historical-loading redraw ownership [frontend/assets/ts/features/charts/session/ChartLoadingIndicator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LifecycleResources } from '@core/lifecyclemodel/LifecycleResources.ts';
import type { RedrawRequest } from '@features/charts/component/chartComponentTypes.ts';

interface ChartLoadingRedrawPort {
    request(request: RedrawRequest): void;
}

interface ChartLoadingIndicatorDependencies {
    state: { readonly isHistoricalDataLoading: boolean };
    redraw: ChartLoadingRedrawPort;
}

class ChartLoadingIndicator {
    readonly #state: ChartLoadingIndicatorDependencies['state'];
    readonly #redraw: ChartLoadingRedrawPort;
    readonly #resources = new LifecycleResources();
    #timer: number | null = null;

    constructor({ state, redraw }: ChartLoadingIndicatorDependencies) {
        this.#state = state;
        this.#redraw = redraw;
    }

    get active(): boolean {
        return this.#state.isHistoricalDataLoading;
    }

    scheduleRedraw(): void {
        if (this.#timer !== null) this.#resources.clearTimer(this.#timer);
        this.#timer = this.#resources.setTimer(() => {
            this.#timer = null;
            this.#redraw.request({ data: true });
        }, 400);
    }

    initialize(signal: AbortSignal): void {
        signal.throwIfAborted();
    }

    async destroy(): Promise<void> {
        this.#timer = null;
        await this.#resources.cleanup();
    }
}

export { ChartLoadingIndicator };
export type { ChartLoadingIndicatorDependencies };
