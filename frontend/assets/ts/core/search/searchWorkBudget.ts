/* SoAI - Cooperative search traversal scheduling [frontend/assets/ts/core/search/searchWorkBudget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { waitForTimerDelay } from '@core/concurrency/timerDelay.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { monotonicMs } from '@core/time/clock.ts';

class SearchWorkBudget {
    readonly #windowRef: Window | null;
    readonly signal: AbortSignal | null;
    #sliceStartedAt = monotonicMs();

    constructor(windowRef: Window | null, signal: AbortSignal | null = null) {
        this.#windowRef = windowRef;
        this.signal = signal;
    }

    async checkpoint(forceYield = false): Promise<void> {
        throwIfAborted(this.signal);
        if (!forceYield && monotonicMs() - this.#sliceStartedAt < 6) return;
        await waitForTimerDelay(this.#windowRef, 0, this.signal);
        throwIfAborted(this.signal);
        this.#sliceStartedAt = monotonicMs();
    }
}

export { SearchWorkBudget };
