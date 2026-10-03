/* SoAI - Page outlet render identity and cancellation ownership [frontend/assets/ts/core/pageoutlet/renderOwnership.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortSignalScope } from '@core/errors/abort.ts';

interface PageOutletRenderScope {
    signal: AbortSignal;
    finish(): void;
}

interface ActivePageOutletRender {
    token: symbol;
    controller: AbortController;
    cleanupSignalScope(): void;
}

class PageOutletRenderOwnership {
    #active: ActivePageOutletRender | null = null;

    begin(token: symbol, callerSignal?: AbortSignal): PageOutletRenderScope {
        this.cancelActive('navigation-superseded');
        const controller = new AbortController();
        const signalScope = createAbortSignalScope([callerSignal, controller.signal]);
        const active: ActivePageOutletRender = {
            token,
            controller,
            cleanupSignalScope: signalScope.cleanup
        };
        this.#active = active;
        return {
            signal: signalScope.signal,
            finish: (): void => {
                signalScope.cleanup();
                if (this.#active === active) {
                    this.#active = null;
                }
            }
        };
    }

    isActive(token: symbol): boolean {
        return this.#active?.token === token;
    }

    cancel(token: symbol, reason: string): void {
        const active = this.#active;
        if (!active || active.token !== token) return;
        this.#active = null;
        active.controller.abort(reason);
        active.cleanupSignalScope();
    }

    cancelActive(reason: string): void {
        const active = this.#active;
        if (active) this.cancel(active.token, reason);
    }
}

export { PageOutletRenderOwnership };
export type { PageOutletRenderScope };
