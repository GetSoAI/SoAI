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

    start(delayMs: number = this.#delayMs): void {
        this.stop();
        this.#timeout = setTimeout(() => {
            this.#timeout = null;
            this.#onTimeout();
        }, delayMs);
    }

    stop(): void {
        if (this.#timeout === null) {
            return;
        }
        clearTimeout(this.#timeout);
        this.#timeout = null;
    }
}

export { TimeoutTimer };
