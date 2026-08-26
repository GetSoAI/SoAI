/* SoAI - Voice call conversation binding state [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallConversationState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';

class VoiceCallConversationState {
    #conversationId: string | null = null;
    #initialBindingPending = false;

    bindInitial(candidate: string | null): void {
        const normalized = toTrimmedString(candidate);
        this.#conversationId = normalized || null;
    }

    get(): string | null {
        return this.#conversationId;
    }

    clear(): void {
        this.#conversationId = null;
        this.#initialBindingPending = false;
    }

    beginSend(): boolean {
        const pending = this.#conversationId === null;
        if (pending) this.#initialBindingPending = true;
        return pending;
    }

    finishSend(pending: boolean, currentConversationId: string | null): boolean {
        if (!pending) return false;
        this.#initialBindingPending = false;
        return this.#conversationId === null && Boolean(toTrimmedString(currentConversationId));
    }

    bindCreated(conversationId: string, currentConversationId: string | null, createdFromEmptyConversation: boolean): boolean {
        if (this.#conversationId !== null || !createdFromEmptyConversation || toTrimmedString(currentConversationId) !== conversationId) return false;
        this.#conversationId = conversationId;
        return true;
    }

    matches(conversationId: string, currentConversationId: string | null): boolean {
        return this.#conversationId === conversationId && toTrimmedString(currentConversationId) === conversationId;
    }

    isInitialPending(): boolean {
        return this.#initialBindingPending;
    }
}

export { VoiceCallConversationState };
