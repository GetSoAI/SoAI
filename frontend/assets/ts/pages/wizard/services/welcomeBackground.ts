/* SoAI - Wizard page welcome background [frontend/assets/ts/pages/wizard/services/welcomeBackground.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { startBlurBlobBackground, type BlurBlobBackgroundCleanup } from '@core/animations/blurBlobBackground.ts';
import { dom } from '@core/dom/dom.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

interface WizardWelcomeBackgroundHost {
    isDomUsable: () => boolean;
    logWarn: (operation: string, error: Error) => void;
}

class WizardWelcomeBackgroundController {
    readonly #host: WizardWelcomeBackgroundHost;
    readonly #timers = new ResourceTracker();
    #cleanup: BlurBlobBackgroundCleanup | null = null;
    #resizeObserver: ResizeObserver | null = null;
    #retryTimerId: number | null = null;
    #retryAttempts = 0;

    constructor(host: WizardWelcomeBackgroundHost) {
        this.#host = host;
    }

    stop(): void {
        if (this.#retryTimerId !== null) {
            this.#timers.clearTimer(this.#retryTimerId);
            this.#retryTimerId = null;
        }
        this.#timers.cleanup();
        if (this.#resizeObserver) {
            this.#resizeObserver.disconnect();
            this.#resizeObserver = null;
        }
        if (this.#cleanup) {
            this.#cleanup();
            this.#cleanup = null;
        }
        this.#retryAttempts = 0;
    }

    start(contentElement: HTMLElement): void {
        this.stop();
        const container = dom.resolve('.wizard-welcome-bg', contentElement);
        if (!(container instanceof HTMLElement)) {
            this.#host.logWarn('welcome-background', new Error('Welcome background container not found'));
            return;
        }
        if (container.clientWidth === 0 || container.clientHeight === 0) {
            this.#waitForContainer(contentElement, container);
            return;
        }
        this.#retryAttempts = 0;
        this.#cleanup = startBlurBlobBackground(container, {
            onError: (operation, error) => this.#host.logWarn(operation, ensureError(error))
        });
    }

    #waitForContainer(contentElement: HTMLElement, container: HTMLElement): void {
        if (typeof ResizeObserver !== 'function') {
            this.#scheduleRetry(contentElement, container);
            return;
        }
        if (this.#resizeObserver) {
            return;
        }
        this.#resizeObserver = new ResizeObserver(() => {
            if (!this.#host.isDomUsable()) {
                return;
            }
            if (!contentElement.isConnected) {
                return;
            }
            if (contentElement.dataset['step'] !== 'welcome') {
                return;
            }
            if (container.clientWidth === 0 || container.clientHeight === 0) {
                return;
            }
            this.stop();
            this.start(contentElement);
        });
        this.#resizeObserver.observe(container);
    }

    #scheduleRetry(contentElement: HTMLElement, container: HTMLElement): void {
        if (this.#retryTimerId !== null) {
            return;
        }
        if (this.#retryAttempts >= 10) {
            this.#host.logWarn('welcome-background', new Error('Welcome background container remained zero-sized'));
            return;
        }
        this.#retryTimerId = this.#timers.setTimeout(() => {
            this.#retryTimerId = null;
            if (!this.#host.isDomUsable()) {
                return;
            }
            if (!contentElement.isConnected) {
                return;
            }
            if (contentElement.dataset['step'] !== 'welcome') {
                return;
            }
            if (container.clientWidth === 0 || container.clientHeight === 0) {
                this.#retryAttempts += 1;
                this.#waitForContainer(contentElement, container);
                return;
            }
            this.start(contentElement);
        }, 50);
    }
}

export { WizardWelcomeBackgroundController };
