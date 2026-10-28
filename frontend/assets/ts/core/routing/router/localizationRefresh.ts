/* SoAI - Navigation-aware localization refresh ownership [frontend/assets/ts/core/routing/router/localizationRefresh.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface RouterLocalizationHost {
    getLanguage(): string;
    getCurrentRoute(): string | null;
    getHashRoute(): string | null;
    getNavigationCompletion(): Promise<void> | null;
    canRefresh(): boolean;
    hasOpenModals(): boolean;
    navigate(route: string): Promise<void>;
    reportFailure(error: Error): void;
}

class RouterLocalizationRefreshController {
    #host: RouterLocalizationHost;
    #renderedLanguage: string | null = null;
    #pending = false;
    #scheduled = false;
    #running = false;
    #resumeRequested = false;
    #disposed = false;

    constructor(host: RouterLocalizationHost) {
        this.#host = host;
    }

    commitRendered(commit: () => void): () => void {
        const language = this.#host.getLanguage();
        return (): void => {
            commit();
            this.#renderedLanguage = language;
        };
    }

    request(): void {
        this.#pending = true;
        this.resume();
    }

    resume(): void {
        if (this.#disposed || !this.#pending || this.#scheduled) return;
        if (this.#running) {
            this.#resumeRequested = true;
            return;
        }
        this.#scheduled = true;
        queueMicrotask(() => {
            this.#scheduled = false;
            if (this.#disposed) return;
            terminateHandledPromise(this.#flush());
        });
    }

    async #flush(): Promise<void> {
        this.#running = true;
        try {
            const navigation = this.#host.getNavigationCompletion();
            if (navigation) await Promise.allSettled([navigation]);
            if (this.#disposed) return;
            if (navigation !== this.#host.getNavigationCompletion()) {
                this.#resumeRequested = true;
                return;
            }
            if (!this.#host.canRefresh() || this.#host.hasOpenModals()) return;
            const route = this.#host.getCurrentRoute();
            if (!route || (this.#host.getHashRoute() !== null && this.#host.getHashRoute() !== route)) return;
            this.#pending = false;
            if (this.#renderedLanguage !== this.#host.getLanguage()) await this.#host.navigate(route);
        } catch (error) {
            this.#pending = false;
            this.#host.reportFailure(ensureError(error));
        } finally {
            this.#running = false;
            if (this.#resumeRequested) {
                this.#resumeRequested = false;
                this.resume();
            }
        }
    }

    dispose(): void {
        this.#disposed = true;
        this.#pending = false;
    }
}

export { RouterLocalizationRefreshController };
