/* SoAI - WebSocket handshake session reconciliation ownership [frontend/assets/ts/core/websocketclient/sessionHandshake.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortScope } from '@core/api/abortScope.ts';
import { handleApiResult } from '@core/api/apiResultHandler.ts';
import { APIError } from '@core/apiError.ts';
import { requireAuthManager } from '@core/auth/runtime.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { LifecycleScope, type LifecycleRun } from '@core/lifecycle/lifecycleScope.ts';
import { RECONNECT_DELAY_MAX_MS } from '@core/websocketclient/constants.ts';

type HandshakeSessionOutcome = 'retry' | 'invalidated' | 'superseded' | 'forbidden' | 'retired';
interface HandshakeSessionResult {
    outcome: HandshakeSessionOutcome;
    run: LifecycleRun;
    authEpoch: number | null;
}

class WebSocketHandshakeReconciliation {
    readonly #scope = new LifecycleScope();
    #task: Promise<HandshakeSessionResult> | null = null;
    #baseUrl: string | null = null;

    get pending(): boolean {
        return this.#task !== null;
    }

    retire(): void {
        this.#scope.abort('WebSocket generation retired');
        this.#task = null;
        this.#baseUrl = null;
    }

    retireForBaseUrl(baseUrl: string | null): void {
        if (this.#baseUrl !== baseUrl) this.retire();
    }

    resolveOutcome(result: HandshakeSessionResult): HandshakeSessionOutcome {
        if (!this.#scope.isCurrent(result.run)) return 'retired';
        const auth = requireAuthManager();
        if (result.authEpoch !== null && result.authEpoch !== auth.authEpoch) return auth.isAuthenticated ? 'superseded' : 'invalidated';
        return result.outcome;
    }

    reconcile(baseUrl: string | null): Promise<HandshakeSessionResult> {
        if (this.#task !== null) return this.#task;
        const run = this.#scope.begin('WebSocket handshake reconciliation');
        this.#baseUrl = baseUrl;
        let authEpoch: number | null = null;
        const task = (async (): Promise<HandshakeSessionOutcome> => {
            const abortScope = createAbortScope(run.signal, RECONNECT_DELAY_MAX_MS);
            try {
                const auth = requireAuthManager();
                authEpoch = auth.authEpoch;
                const result = await raceWithAbortSignal(auth.reconcileSession(abortScope.signal), abortScope.signal);
                authEpoch = result.authEpoch;
                if (!this.#scope.isCurrent(run)) return 'retired';
                return result.status === 'confirmed' ? 'retry' : result.status;
            } catch (error) {
                if (!this.#scope.isCurrent(run)) return 'retired';
                const runtimeError = ensureError(error);
                if (runtimeError instanceof APIError && runtimeError.status === 403) {
                    const outcome = this.resolveOutcome({ outcome: 'forbidden', run, authEpoch });
                    if (outcome !== 'forbidden') return outcome;
                    try {
                        await handleApiResult(Promise.reject(runtimeError), { logErrors: false, rethrow: false, boundaryName: 'WebSocketClient', shouldNotify: (): boolean => this.resolveOutcome({ outcome: 'forbidden', run, authEpoch }) === 'forbidden' });
                    } catch (notificationError) {
                        errorHandler.warn('WebSocketClient', 'Session permission notification failed', ensureError(notificationError));
                    }
                    return this.#scope.isCurrent(run) ? 'forbidden' : 'retired';
                }
                errorHandler.debug('WebSocketClient', 'Handshake session remains unconfirmed', runtimeError);
                return 'retry';
            } finally {
                abortScope.cleanup();
            }
        })()
            .then((outcome): HandshakeSessionResult => ({ outcome, run, authEpoch }))
            .finally(() => {
                if (this.#task === task) this.#task = null;
            });
        this.#task = task;
        return task;
    }
}

export { WebSocketHandshakeReconciliation };
export type { HandshakeSessionOutcome, HandshakeSessionResult };
