/* SoAI - Updates page control layer operation monitor controller [frontend/assets/ts/pages/updates/controllers/updatesOperationMonitorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface UpdatesOperationMonitorHost {
    setTimeout: (callback: () => void, delayMs: number) => number | null;
    clearTimer: (timerId: number | null) => void;
    onTimeout: () => void;
}

class UpdatesOperationMonitor {
    readonly #host: UpdatesOperationMonitorHost;
    readonly #timeoutMs: number;
    #revision = 0;
    #timerId: number | null = null;
    #timedOutRevision: number | null = null;

    constructor(host: UpdatesOperationMonitorHost, timeoutMs: number) {
        this.#host = host;
        this.#timeoutMs = timeoutMs;
    }

    begin(): number {
        this.#revision += 1;
        const revision = this.#revision;
        this.#timedOutRevision = null;
        this.clearTimer();
        this.#timerId = this.#host.setTimeout(() => {
            if (this.isCurrent(revision)) {
                this.#timedOutRevision = revision;
                this.#host.onTimeout();
            }
        }, this.#timeoutMs);
        return revision;
    }

    finish(revision: number): void {
        if (this.isCurrent(revision)) {
            this.clearTimer();
        }
    }

    finishAndCanApply(revision: number, allowTimedOut: boolean): boolean {
        if (!this.isCurrent(revision)) {
            return false;
        }
        const timedOut = this.hasTimedOut(revision);
        this.finish(revision);
        return allowTimedOut || !timedOut;
    }

    invalidate(): void {
        this.#revision += 1;
        this.#timedOutRevision = null;
        this.clearTimer();
    }

    isCurrent(revision: number): boolean {
        return revision === this.#revision;
    }

    hasTimedOut(revision: number): boolean {
        return revision === this.#timedOutRevision;
    }

    clearTimer(): void {
        this.#host.clearTimer(this.#timerId);
        this.#timerId = null;
    }
}

export { UpdatesOperationMonitor };
