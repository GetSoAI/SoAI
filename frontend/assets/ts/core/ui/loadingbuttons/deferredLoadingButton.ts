/* SoAI - Threshold gated button loading state [frontend/assets/ts/core/ui/loadingbuttons/deferredLoadingButton.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindow } from '@core/environment/public.ts';
import { beginLoadingButtonWithClear, coerceBusyDisabledTarget } from '@core/ui/loadingbuttons/service.ts';

const DEFERRED_BUTTON_LOADING_DELAY_MS = 250;

class DeferredButtonLoading {
    #timeoutId: number | null = null;
    #clearLoading: (() => void) | null = null;

    begin(button: HTMLElement | null): void {
        this.settle();
        const busyTarget = button === null ? null : coerceBusyDisabledTarget(button);
        if (busyTarget === null) {
            return;
        }
        this.#timeoutId = getWindow().setTimeout(() => {
            this.#timeoutId = null;
            this.#clearLoading = beginLoadingButtonWithClear(busyTarget);
        }, DEFERRED_BUTTON_LOADING_DELAY_MS);
    }

    settle(): void {
        if (this.#timeoutId !== null) {
            getWindow().clearTimeout(this.#timeoutId);
            this.#timeoutId = null;
        }
        if (this.#clearLoading !== null) {
            this.#clearLoading();
            this.#clearLoading = null;
        }
    }
}

export { DeferredButtonLoading, DEFERRED_BUTTON_LOADING_DELAY_MS };
