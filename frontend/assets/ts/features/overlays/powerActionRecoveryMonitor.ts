/* SoAI - Power action recovery evidence monitor [frontend/assets/ts/features/overlays/powerActionRecoveryMonitor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handleApiResult } from '@core/api/apiResultHandler.ts';
import type { ApiClient } from '@core/api/service.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import { startPollingLoop, type PollingLoopHandle } from '@core/concurrency/pollingLoop.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { POLL_INTERVAL_MS, REQUEST_TIMEOUT_MS, type PowerActionKey } from '@features/overlays/powerActionConfig.ts';
import { observePowerTransition } from '@features/overlays/powerTransitionObservation.ts';

const RESUME_GAP_EVIDENCE_MS = POLL_INTERVAL_MS * 3;

interface PowerActionRecoveryCallbacks {
    canPoll: () => boolean;
    onInterrupted: () => void;
    onRecovered: () => void;
}

class PowerActionRecoveryMonitor {
    readonly #api: ApiClient;
    readonly #callbacks: PowerActionRecoveryCallbacks;
    readonly #lifecycle = new LifecycleScope();
    #action: PowerActionKey | null = null;
    #interruptionObserved = false;
    #lastProbeTiming: { wallMs: number; monotonicMs: number } | null = null;
    #pollingSuspended = false;
    #pollingHandle: PollingLoopHandle | null = null;
    #transportUnsubscribe: (() => void) | null = null;

    constructor(api: ApiClient, callbacks: PowerActionRecoveryCallbacks) {
        this.#api = api;
        this.#callbacks = callbacks;
    }

    start(action: PowerActionKey): void {
        this.stop();
        const run = this.#lifecycle.begin('power-action-monitor-start');
        this.#action = action;
        this.#pollingSuspended = !this.#callbacks.canPoll();
        this.#resetProbeTiming();
        this.#transportUnsubscribe = observePowerTransition({
            onInterrupted: () => {
                if (this.#lifecycle.isCurrent(run)) this.#markInterrupted();
            },
            onConnected: () => {
                if (this.#lifecycle.isCurrent(run)) this.#startPolling();
            }
        });
        this.#startPolling();
    }

    suspendPolling(): void {
        this.#observeResumeEvidence();
        this.#stopPolling();
        this.#pollingSuspended = true;
    }

    resumePolling(): void {
        if (this.#action === null) return;
        this.#observeResumeEvidence();
        this.#pollingSuspended = false;
        this.#resetProbeTiming();
        this.#startPolling();
    }

    stop(): void {
        this.#lifecycle.abort('power-action-monitor-stop');
        this.#stopPolling();
        this.#transportUnsubscribe?.();
        this.#transportUnsubscribe = null;
        this.#action = null;
        this.#interruptionObserved = false;
        this.#lastProbeTiming = null;
        this.#pollingSuspended = false;
    }

    async #probe(signal: AbortSignal): Promise<boolean> {
        const action = this.#action;
        if (action === null) return true;
        throwIfAborted(signal);
        this.#observeResumeEvidence();
        try {
            throwIfAborted(signal);
            const systemApi = this.#api.system;
            if (!isObject(systemApi) || !isFunction(systemApi.health) || !isFunction(systemApi.status)) {
                throw new Error('PowerActionRecoveryMonitor requires system health and status APIs');
            }
            const options: RequestOptions = { timeoutMs: REQUEST_TIMEOUT_MS, signal };
            const health = await handleApiResult(systemApi.health(options), {
                boundaryName: 'PowerActionRecoveryMonitor',
                silent: true,
                notifyOnError: false,
                rethrow: false,
                logErrors: false
            });
            throwIfAborted(signal);
            if (!health) {
                this.#markInterrupted();
                return false;
            }
            if (!this.#interruptionObserved) return false;
            const status = await handleApiResult(systemApi.status(), {
                boundaryName: 'PowerActionRecoveryMonitor',
                silent: true,
                notifyOnError: false,
                rethrow: false,
                logErrors: false
            });
            throwIfAborted(signal);
            if (!status || status.mainState === 'stopping') return false;
            const initialized = await handleApiResult(this.#api.initialize(), {
                boundaryName: 'PowerActionRecoveryMonitor',
                silent: true,
                notifyOnError: false,
                rethrow: false,
                logErrors: false
            });
            throwIfAborted(signal);
            if (!initialized) return false;
            this.#callbacks.onRecovered();
            return true;
        } finally {
            if (!signal.aborted && this.#action === action) this.#resetProbeTiming();
        }
    }

    #resetProbeTiming(): void {
        this.#lastProbeTiming = { wallMs: Date.now(), monotonicMs: monotonicMs() };
    }

    #observeResumeEvidence(): void {
        const previous = this.#lastProbeTiming;
        if ((this.#action !== 'suspendSystem' && this.#action !== 'hibernateSystem') || previous === null) return;
        const wallElapsed = Date.now() - previous.wallMs;
        const elapsed = this.#pollingSuspended ? wallElapsed - (monotonicMs() - previous.monotonicMs) : wallElapsed;
        if (elapsed >= RESUME_GAP_EVIDENCE_MS) this.#markInterrupted();
    }

    #markInterrupted(): void {
        if (this.#interruptionObserved) return;
        this.#interruptionObserved = true;
        this.#callbacks.onInterrupted();
    }

    #startPolling(): void {
        if (this.#action === null || !this.#callbacks.canPoll()) return;
        this.#stopPolling();
        this.#pollingHandle = startPollingLoop({
            label: 'power-action-monitor',
            intervalMs: POLL_INTERVAL_MS,
            run: async ({ signal }): Promise<'continue' | 'stop'> => {
                const recovered = await this.#probe(signal);
                return recovered ? 'stop' : 'continue';
            },
            onError: (error): 'continue' => {
                errorHandler.warn('PowerActionRecoveryMonitor', 'Completion probe failed', ensureError(error));
                return 'continue';
            }
        });
    }

    #stopPolling(): void {
        this.#pollingHandle?.stop('power-action-monitor-stop');
        this.#pollingHandle = null;
    }
}

export { PowerActionRecoveryMonitor };
