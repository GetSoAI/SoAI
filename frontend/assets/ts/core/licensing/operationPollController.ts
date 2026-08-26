/* SoAI - Durable licensing operation observation [frontend/assets/ts/core/licensing/operationPollController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isLicensingOperationInProgress } from '@core/licensing/operationLifecycle.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

interface LicensingOperationPollStatus {
    draftRevision: number;
    operation: { state: string; attemptCount: number; updatedAtMs: number } | null;
}

interface LicensingOperationPollHost<Status extends LicensingOperationPollStatus> {
    fetchStatus(signal: AbortSignal): Promise<Status>;
    onStatus(status: Status): void;
    onFailure(error: Error): void;
}

const requiresPolling = (status: LicensingOperationPollStatus): boolean => {
    return status.operation !== null && isLicensingOperationInProgress(status.operation.state);
};

const progressIdentity = (status: LicensingOperationPollStatus): string => {
    const operation = status.operation;
    return operation === null ? `${String(status.draftRevision)}:none` : `${String(status.draftRevision)}:${operation.state}:${String(operation.attemptCount)}:${String(operation.updatedAtMs)}`;
};

class LicensingOperationPollController<Status extends LicensingOperationPollStatus> {
    readonly #host: LicensingOperationPollHost<Status>;
    readonly #timers = new ResourceTracker();
    #timerId: number | null = null;
    #requestController: AbortController | null = null;
    #active = false;
    #destroyed = false;
    #delayMs = 1_000;
    #progressIdentity = '';
    readonly #visibilityListener = (): void => this.#handleVisibilityChange();

    constructor(host: LicensingOperationPollHost<Status>) {
        this.#host = host;
        document.addEventListener('visibilitychange', this.#visibilityListener, { passive: true });
    }

    update(status: Status): void {
        if (this.#destroyed) return;
        this.#active = requiresPolling(status);
        const nextProgressIdentity = progressIdentity(status);
        if (this.#progressIdentity !== nextProgressIdentity) this.#delayMs = 1_000;
        this.#progressIdentity = nextProgressIdentity;
        if (!this.#active) {
            this.#stopPendingWork();
            return;
        }
        this.#schedule();
    }

    pause(): void {
        this.#active = false;
        this.#stopPendingWork();
    }

    destroy(): void {
        if (this.#destroyed) return;
        this.#destroyed = true;
        this.#active = false;
        document.removeEventListener('visibilitychange', this.#visibilityListener);
        this.#stopPendingWork();
        this.#timers.cleanup();
    }

    #handleVisibilityChange(): void {
        if (!this.#active || this.#destroyed) return;
        if (document.visibilityState === 'hidden') {
            this.#clearTimer();
            return;
        }
        this.#schedule();
    }

    #schedule(): void {
        if (!this.#active || this.#destroyed || document.visibilityState === 'hidden') return;
        if (this.#timerId !== null || this.#requestController !== null) return;
        this.#timerId = this.#timers.setTimeout(() => {
            this.#timerId = null;
            void this.#poll().catch((error) => {
                errorHandler.error('LicensingOperationPollController', 'Licensing poll escaped its request boundary', ensureError(error));
            });
        }, this.#delayMs);
    }

    async #poll(): Promise<void> {
        if (!this.#active || this.#destroyed || document.visibilityState === 'hidden') return;
        const requestController = new AbortController();
        this.#requestController = requestController;
        const previousProgress = this.#progressIdentity;
        try {
            const status = await this.#host.fetchStatus(requestController.signal);
            if (this.#destroyed || requestController.signal.aborted || this.#requestController !== requestController) return;
            this.#host.onStatus(status);
            this.#active = requiresPolling(status);
            this.#progressIdentity = progressIdentity(status);
            this.#delayMs = this.#progressIdentity === previousProgress ? Math.min(this.#delayMs * 2, 15_000) : 1_000;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!requestController.signal.aborted && !this.#destroyed && !isAbortError(runtimeError)) {
                this.#host.onFailure(runtimeError);
                this.#delayMs = Math.min(this.#delayMs * 2, 15_000);
            }
        } finally {
            if (this.#requestController === requestController) this.#requestController = null;
            this.#schedule();
        }
    }

    #stopPendingWork(): void {
        this.#clearTimer();
        this.#requestController?.abort();
        this.#requestController = null;
    }

    #clearTimer(): void {
        if (this.#timerId === null) return;
        this.#timers.clearTimeout(this.#timerId);
        this.#timerId = null;
    }
}

export { LicensingOperationPollController };
export type { LicensingOperationPollHost, LicensingOperationPollStatus };
