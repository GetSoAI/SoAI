/* SoAI - Retryable conversation regeneration state [frontend/assets/ts/features/chat/conversationinputs/ConversationRegenerationRetryStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationRegenerationReceipt } from '@core/api/contracts/webuiMessageRegenerationContracts.ts';
import type { RetryableConversationRegeneration } from '@features/chat/conversationinputs/ConversationInputTypes.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const projectRetryableRegeneration = (receipt: ConversationRegenerationReceipt): RetryableConversationRegeneration => ({
    inputId: receipt.inputId,
    acceptedAtMs: receipt.acceptedAtMs,
    contentPreviewFeedback: receipt.contentPreviewFeedback,
    previewContractFeedback: receipt.previewContractFeedback
});

class ConversationRegenerationRetryStore {
    readonly #receiptByConversationId = new Map<string, ConversationRegenerationReceipt>();
    readonly #latestObservationByConversationId = new Map<string, { inputId: string; revision: number; terminal: boolean }>();

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

    observe(conversationId: string, receipt: ConversationRegenerationReceipt): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) return;
        const terminal = receipt.state === 'completed' || receipt.state === 'failed' || receipt.state === 'cancelled' || receipt.state === 'effect_unknown';
        const latest = this.#latestObservationByConversationId.get(normalizedConversationId);
        if (latest && receipt.lastModifiedAtMs < latest.revision) return;
        if (latest && receipt.lastModifiedAtMs === latest.revision && (latest.inputId !== receipt.inputId || latest.terminal)) return;
        this.#latestObservationByConversationId.set(normalizedConversationId, { inputId: receipt.inputId, revision: receipt.lastModifiedAtMs, terminal });
        if ((receipt.state === 'failed' || receipt.state === 'cancelled') && !receipt.hasAssistantReplacement) {
            this.#receiptByConversationId.set(normalizedConversationId, receipt);
            return;
        }
        this.#receiptByConversationId.delete(normalizedConversationId);
    }

    clearIfMatches(conversationId: string, inputId: string): void {
        if (this.#receiptByConversationId.get(conversationId)?.inputId === inputId) {
            this.#receiptByConversationId.delete(conversationId);
        }
    }
}

export { ConversationRegenerationRetryStore };
