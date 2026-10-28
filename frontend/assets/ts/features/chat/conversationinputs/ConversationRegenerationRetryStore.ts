/* SoAI - Retryable conversation regeneration state [frontend/assets/ts/features/chat/conversationinputs/ConversationRegenerationRetryStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationRegenerationReceipt } from '@core/api/contracts/webuiMessageRegenerationContracts.ts';
import { isConversationInputTerminalState } from '@core/chat/conversationInputLifecycle.ts';
import type { RetryableConversationRegeneration } from '@features/chat/conversationinputs/ConversationInputTypes.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const projectRetryableRegeneration = (receipt: ConversationRegenerationReceipt): RetryableConversationRegeneration => ({
    inputId: receipt.inputId,
    acceptedAtMs: receipt.acceptedAtMs,
    contentPreviewFeedback: receipt.contentPreviewFeedback,
    previewContractFeedback: receipt.previewContractFeedback
});

interface RegenerationObservation {
    inputId: string;
    revision: number;
    terminal: boolean;
    retryable: boolean;
}

const revisesSameRevisionObservation = (latest: RegenerationObservation, receipt: ConversationRegenerationReceipt, terminal: boolean): boolean => latest.inputId === receipt.inputId && (!latest.terminal || (terminal && latest.retryable !== receipt.isRetryable));

class ConversationRegenerationRetryStore {
    readonly #receiptByConversationId = new Map<string, ConversationRegenerationReceipt>();
    readonly #latestObservationByConversationId = new Map<string, RegenerationObservation>();

    reset(): void {
        this.#receiptByConversationId.clear();
        this.#latestObservationByConversationId.clear();
    }

    get(conversationId: string): RetryableConversationRegeneration | null {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const receipt = normalizedConversationId ? this.#receiptByConversationId.get(normalizedConversationId) : undefined;
        return receipt ? projectRetryableRegeneration(receipt) : null;
    }

    requireInput(conversationId: string, inputId: string): { conversationId: string; regeneration: RetryableConversationRegeneration } {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const receipt = normalizedConversationId ? this.#receiptByConversationId.get(normalizedConversationId) : undefined;
        if (!normalizedConversationId || receipt?.inputId !== inputId) {
            throw new Error('Conversation regeneration retry is no longer available.');
        }
        return {
            conversationId: normalizedConversationId,
            regeneration: projectRetryableRegeneration(receipt)
        };
    }

    observe(conversationId: string, receipt: ConversationRegenerationReceipt): boolean {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) return false;
        const terminal = isConversationInputTerminalState(receipt.state);
        const latest = this.#latestObservationByConversationId.get(normalizedConversationId);
        if (latest && receipt.lastModifiedAtMs < latest.revision) return false;
        if (latest && receipt.lastModifiedAtMs === latest.revision && !revisesSameRevisionObservation(latest, receipt, terminal)) return false;
        this.#latestObservationByConversationId.set(normalizedConversationId, { inputId: receipt.inputId, revision: receipt.lastModifiedAtMs, terminal, retryable: receipt.isRetryable });
        if (receipt.isRetryable) {
            this.#receiptByConversationId.set(normalizedConversationId, receipt);
            return true;
        }
        this.#receiptByConversationId.delete(normalizedConversationId);
        return true;
    }

    withdraw(conversationId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const latest = this.#latestObservationByConversationId.get(normalizedConversationId);
        if (latest) this.#latestObservationByConversationId.set(normalizedConversationId, { ...latest, retryable: false });
        this.#receiptByConversationId.delete(normalizedConversationId);
    }

    clearIfMatches(conversationId: string, inputId: string): void {
        if (this.#receiptByConversationId.get(conversationId)?.inputId === inputId) {
            this.#receiptByConversationId.delete(conversationId);
        }
    }
}

export { ConversationRegenerationRetryStore };
