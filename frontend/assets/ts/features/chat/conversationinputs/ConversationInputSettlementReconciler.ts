/* SoAI - Conversation input settlement reconciliation [frontend/assets/ts/features/chat/conversationinputs/ConversationInputSettlementReconciler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { raceWithAbortSignal } from '@core/errors/abort.ts';
import { sleepMsAbortable } from '@core/primitives/sleepMsAbortable.ts';
import type { ConversationInputStateStore } from '@features/chat/conversationinputs/ConversationInputStateStore.ts';

interface ConversationInputSettlementDependencies {
    store: ConversationInputStateStore;
    signal: AbortSignal;
    reconcileSettledConversationInputs: (conversationId: string) => Promise<void>;
}

const SETTLEMENT_RECONCILIATION_RETRY_DELAYS_MS: readonly number[] = [250, 1000, 3000];

class ConversationInputSettlementReconciler {
    readonly #dependencies: ConversationInputSettlementDependencies;
    readonly #settlementReconciliationByConversationId = new Map<string, Promise<void>>();

    constructor(dependencies: ConversationInputSettlementDependencies) {
        this.#dependencies = dependencies;
    }

    dispose(): void {
        this.#settlementReconciliationByConversationId.clear();
    }

    async reconcile(conversationId: string): Promise<void> {
        const signal = this.#dependencies.signal;
        while (!signal.aborted) {
            const activeReconciliation = this.#settlementReconciliationByConversationId.get(conversationId);
            if (activeReconciliation) {
                await raceWithAbortSignal(activeReconciliation, signal);
                continue;
            }
            const inputIds = this.#dependencies.store.takePendingSettlements(conversationId);
            if (inputIds.length === 0) {
                return;
            }
            const reconciliation = this.#reconcileSettlementBatch(conversationId, inputIds);
            this.#settlementReconciliationByConversationId.set(conversationId, reconciliation);
            try {
                await raceWithAbortSignal(reconciliation, signal);
            } finally {
                if (this.#settlementReconciliationByConversationId.get(conversationId) === reconciliation) {
                    this.#settlementReconciliationByConversationId.delete(conversationId);
                }
            }
        }
    }

    async #reconcileSettlementBatch(conversationId: string, inputIds: readonly string[]): Promise<void> {
        const signal = this.#dependencies.signal;
        for (let attemptIndex = 0; ; attemptIndex += 1) {
            try {
                await this.#dependencies.reconcileSettledConversationInputs(conversationId);
                if (!signal.aborted) {
                    this.#dependencies.store.completeSettlements(conversationId, inputIds);
                }
                return;
            } catch (error) {
                const retryDelayMs = SETTLEMENT_RECONCILIATION_RETRY_DELAYS_MS[attemptIndex];
                if (signal.aborted || retryDelayMs === undefined) {
                    if (!signal.aborted) {
                        this.#dependencies.store.restorePendingSettlements(conversationId, inputIds);
                    }
                    throw error;
                }
                await sleepMsAbortable(signal, retryDelayMs);
            }
        }
    }
}

export { ConversationInputSettlementReconciler };
