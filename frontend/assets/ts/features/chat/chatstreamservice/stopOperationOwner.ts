/* SoAI - Request-fenced Chat Stop operation owner [frontend/assets/ts/features/chat/chatstreamservice/stopOperationOwner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { monotonicMs } from '@core/time/clock.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import type { ChatStreamStopApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';

const STOP_DEADLINE_MS = 5000;

type ChatStopOutcome = 'terminal' | 'failed' | 'unconfirmed';

interface StopOperation {
    requestId: string;
    forcePendingSteers: boolean;
    startedAtMs: number;
    state: 'stopping' | ChatStopOutcome;
    promise: Promise<ChatStopOutcome>;
    resolve: (outcome: ChatStopOutcome) => void;
    timer: TimeoutTimer;
    terminalListeners: Set<() => void>;
    reconciliationStarted: boolean;
}

type ChatStopTerminalReconciler = (conversationId: string, requestId: string) => Promise<boolean>;

class ChatStreamStopOperationOwner {
    readonly #apiClient: ChatStreamStopApiClient;
    readonly #reconcileTerminal: ChatStopTerminalReconciler;
    readonly #operations = new Map<string, StopOperation>();

    constructor(apiClient: ChatStreamStopApiClient, reconcileTerminal: ChatStopTerminalReconciler) {
        this.#apiClient = apiClient;
        this.#reconcileTerminal = reconcileTerminal;
    }

    request(input: { conversationId: string; requestId: string; forcePendingSteers: boolean; onTerminalEvidence?: () => void }): Promise<ChatStopOutcome> {
        const existing = this.#operations.get(input.conversationId);
        if (existing?.requestId === input.requestId && existing.state === 'stopping') {
            if (input.onTerminalEvidence !== undefined) existing.terminalListeners.add(input.onTerminalEvidence);
            return existing.promise;
        }
        if (existing !== undefined) {
            existing.timer.stop();
            if (existing.state === 'stopping') existing.resolve('unconfirmed');
        }
        const deferred = createDeferred<ChatStopOutcome>();
        const operation: StopOperation = {
            requestId: input.requestId,
            forcePendingSteers: input.forcePendingSteers,
            startedAtMs: monotonicMs(),
            state: 'stopping',
            promise: deferred.promise,
            resolve: deferred.resolve,
            timer: new TimeoutTimer(STOP_DEADLINE_MS, () => this.#handleDeadline(input.conversationId, operation)),
            terminalListeners: new Set(input.onTerminalEvidence === undefined ? [] : [input.onTerminalEvidence]),
            reconciliationStarted: false
        };
        this.#operations.set(input.conversationId, operation);
        operation.timer.start();
        terminateHandledPromise(this.#requestCancellation(input.conversationId, operation));
        return deferred.promise;
    }

    settleTerminal(conversationId: string, requestId: string): void {
        const operation = this.#operations.get(conversationId);
        if (operation?.requestId !== requestId || operation.state === 'terminal') return;
        this.#settle(conversationId, operation, 'terminal');
    }

    dispose(): void {
        for (const operation of this.#operations.values()) {
            operation.timer.stop();
            if (operation.state === 'stopping') operation.resolve('unconfirmed');
            operation.terminalListeners.clear();
        }
        this.#operations.clear();
    }

    async #requestCancellation(conversationId: string, operation: StopOperation): Promise<void> {
        try {
            const response = await this.#apiClient.webui.chat.streamCancellation.request(
                conversationId,
                {
                    requestId: operation.requestId,
                    forcePendingSteers: operation.forcePendingSteers
                },
                { timeoutMs: STOP_DEADLINE_MS }
            );
            if (!this.#isCurrent(conversationId, operation)) return;
            if (response.conversationId !== conversationId || response.requestId !== operation.requestId) {
                throw new Error('Chat Stop response identity did not match the request.');
            }
            if (response.status === 'already_terminal' || response.status === 'superseded') {
                await this.#reconcile(conversationId, operation);
            }
        } catch {
            if (!this.#isCurrent(conversationId, operation) || operation.state !== 'stopping') return;
            if (monotonicMs() - operation.startedAtMs >= STOP_DEADLINE_MS) {
                this.#settle(conversationId, operation, 'unconfirmed');
                terminateHandledPromise(this.#reconcile(conversationId, operation));
                return;
            }
            this.#settle(conversationId, operation, 'failed');
        }
    }

    #handleDeadline(conversationId: string, operation: StopOperation): void {
        if (!this.#isCurrent(conversationId, operation) || operation.state !== 'stopping') return;
        if (monotonicMs() - operation.startedAtMs < STOP_DEADLINE_MS) {
            operation.timer.start(STOP_DEADLINE_MS - (monotonicMs() - operation.startedAtMs));
            return;
        }
        this.#settle(conversationId, operation, 'unconfirmed');
        terminateHandledPromise(this.#reconcile(conversationId, operation));
    }

    async #reconcile(conversationId: string, operation: StopOperation): Promise<void> {
        if (operation.reconciliationStarted) return;
        operation.reconciliationStarted = true;
        const terminal = await this.#reconcileTerminal(conversationId, operation.requestId);
        if (!this.#isCurrent(conversationId, operation)) return;
        if (terminal) this.#settle(conversationId, operation, 'terminal');
    }

    #isCurrent(conversationId: string, operation: StopOperation): boolean {
        return this.#operations.get(conversationId) === operation;
    }

    #settle(conversationId: string, operation: StopOperation, outcome: ChatStopOutcome): void {
        if (operation.state === outcome) return;
        operation.timer.stop();
        operation.state = outcome;
        operation.resolve(outcome);
        if (outcome === 'terminal') {
            for (const listener of operation.terminalListeners) listener();
            operation.terminalListeners.clear();
            if (this.#operations.get(conversationId) === operation) this.#operations.delete(conversationId);
        }
    }
}

export { ChatStreamStopOperationOwner, STOP_DEADLINE_MS };
export type { ChatStopOutcome, ChatStopTerminalReconciler };
