/* SoAI - Shared page outlet delayed loading [frontend/assets/ts/core/pageoutlet/delayedLoading.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { getPerformance } from '@core/environment/public.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';

const DELAYED_LOADING_LABEL_MS = 5000;
const DELAYED_LOADING_ERROR_MS = 30000;
const DELAYED_LOADING_TICK_MS = 250;

class DelayedPageOutletLoading {
    #resources: ResourceTracker;
    #tickTimer: number | null = null;
    #startedAt: number | null = null;
    #showLoading: (label: string | null, detail: string | null, delayed: boolean) => void;

    constructor(options: { resources: ResourceTracker; showLoading: (label: string | null, detail: string | null, delayed: boolean) => void }) {
        this.#resources = options.resources;
        this.#showLoading = options.showLoading;
    }

    schedule(): void {
        this.cancel();
        this.#startedAt = getPerformance().now();
        this.#showLoading(null, null, true);
        this.#tickTimer = this.#resources.setInterval(() => this.#renderElapsedState(), DELAYED_LOADING_TICK_MS);
    }

    cancel(): void {
        if (this.#tickTimer !== null) {
            this.#resources.clearTimer(this.#tickTimer);
            this.#tickTimer = null;
        }
        this.#startedAt = null;
    }

    #renderElapsedState(): void {
        if (this.#startedAt === null) {
            return;
        }
        const elapsedMs = getPerformance().now() - this.#startedAt;
        if (elapsedMs >= DELAYED_LOADING_ERROR_MS) {
            this.#showLoading(null, i18n.t('pageOutlet.loadingDelayError'), false);
            return;
        }
        if (elapsedMs >= DELAYED_LOADING_LABEL_MS) {
            this.#showLoading(i18n.t('pageOutlet.loadingLabel'), null, false);
        }
    }
}

export { DelayedPageOutletLoading };
