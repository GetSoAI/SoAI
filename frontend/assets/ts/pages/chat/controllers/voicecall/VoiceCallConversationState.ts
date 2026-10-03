/* SoAI - Voice call conversation binding state [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallConversationState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';

class VoiceCallConversationState {
    #conversationId: string | null = null;
    readonly #sendSequence = new SequenceToken();
    #pendingInitialSend: number | null = null;

    bindInitial(candidate: string | null): void {
        const normalized = toTrimmedString(candidate);
        this.#conversationId = normalized || null;
    }

    get(): string | null {
        return this.#conversationId;
    }

    clear(): void {
        this.#conversationId = null;
        this.#sendSequence.invalidate();
        this.#pendingInitialSend = null;
    }

    beginSend(): number | null {
        if (this.#conversationId !== null) return null;
        const token = this.#sendSequence.next();
        this.#pendingInitialSend = token;
        return token;
    }

    finishSend(token: number | null, currentConversationId: string | null): boolean {
        if (token === null || this.#pendingInitialSend !== token) return false;
        this.#pendingInitialSend = null;
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
        return this.#pendingInitialSend !== null;
    }
}

export { VoiceCallConversationState };
