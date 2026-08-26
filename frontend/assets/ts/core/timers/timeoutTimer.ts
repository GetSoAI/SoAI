/* SoAI - Shared timers timeout timer [frontend/assets/ts/core/timers/timeoutTimer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class TimeoutTimer {
    #timeout: ReturnType<typeof setTimeout> | null = null;
    readonly #delayMs: number;
    readonly #onTimeout: () => void;

    constructor(delayMs: number, onTimeout: () => void) {
        this.#delayMs = delayMs;
        this.#onTimeout = onTimeout;
    }

    start(): void {
        this.stop();
        this.#timeout = setTimeout(() => {
            this.#timeout = null;
            this.#onTimeout();
        }, this.#delayMs);
    }

    stop(): void {
        if (!this.#timeout) {
            return;
        }
        clearTimeout(this.#timeout);
        this.#timeout = null;
    }
}

export { TimeoutTimer };
