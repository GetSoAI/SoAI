/* SoAI - Chat stream admission state [frontend/assets/ts/features/chat/chatstreamservice/admissionState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamAdmissionStatus, ChatStreamLifecycle, ChatStreamStatusSnapshot } from '@features/chat/chatstreamservice/activeStreamStatus.ts';
import { compareChatStreamMessageOrderIdentities, type ChatStreamMessageOrderIdentity } from '@features/chat/chatstreamservice/streamIdentity.ts';
import type { ChatTurnAdmissionStreamIdentity } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type ChatStreamAdmissionIdentity = ChatStreamMessageOrderIdentity & {
    requestId: string;
};

type ChatStreamAdmissionConversationIdentity = ChatStreamAdmissionIdentity & {
    conversationId: string;
};

const INACTIVE_ADMISSION: ChatStreamAdmissionStatus = {
    streamLifecycle: 'inactive',
    canAcceptConversationInput: false,
    canStartNextPrompt: true,
    canAcceptSteerPrompt: false,
    activeToolCallCount: 0
};

class ChatStreamAdmissionState {
    readonly #admissionByConversationId = new Map<string, ChatStreamAdmissionStatus>();
    readonly #identityByConversationId = new Map<string, ChatStreamAdmissionIdentity>();

    #setLifecycle(identity: ChatStreamAdmissionConversationIdentity, streamLifecycle: ChatStreamLifecycle): void {
        const normalizedConversationId = normalizeConversationId(identity.conversationId);
        if (!normalizedConversationId) {
            return;
        }
        const current = this.#admissionByConversationId.get(normalizedConversationId) ?? INACTIVE_ADMISSION;
        const currentIdentity = this.#identityByConversationId.get(normalizedConversationId) ?? null;
        if (streamLifecycle === 'terminalizing' && current.streamLifecycle === 'inactive' && currentIdentity === null) {
            return;
        }
        if (currentIdentity !== null && compareChatStreamMessageOrderIdentities(identity, currentIdentity) < 0) {
            return;
        }
        if (current.streamLifecycle === 'terminalizing' && streamLifecycle === 'streaming' && currentIdentity !== null && compareChatStreamMessageOrderIdentities(identity, currentIdentity) === 0) {
            return;
        }
        this.#admissionByConversationId.set(normalizedConversationId, {
            streamLifecycle,
            canAcceptConversationInput: streamLifecycle !== 'inactive',
            canStartNextPrompt: streamLifecycle === 'inactive',
            canAcceptSteerPrompt: streamLifecycle === 'streaming',
            activeToolCallCount: streamLifecycle === 'inactive' ? 0 : current.activeToolCallCount
        });
        this.#identityByConversationId.set(normalizedConversationId, identity);
    }

    update(status: ChatStreamStatusSnapshot): void {
        const current = this.#admissionByConversationId.get(status.conversationId) ?? null;
        if (current?.streamLifecycle === 'terminalizing' && status.active && status.admission.streamLifecycle === 'streaming') {
            const currentIdentity = this.#identityByConversationId.get(status.conversationId) ?? null;
            if (currentIdentity !== null && compareChatStreamMessageOrderIdentities(status, currentIdentity) <= 0) {
                return;
            }
        }
        this.#admissionByConversationId.set(status.conversationId, status.admission);
        if (status.active) {
            this.#identityByConversationId.set(status.conversationId, status);
        } else {
            this.#identityByConversationId.delete(status.conversationId);
        }
    }

    markStreaming(identity: ChatStreamAdmissionConversationIdentity): void {
        this.#setLifecycle(identity, 'streaming');
    }

    markTerminalizing(identity: ChatStreamAdmissionConversationIdentity): void {
        this.#setLifecycle(identity, 'terminalizing');
    }

    markInactive(conversationId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        this.#admissionByConversationId.set(normalizedConversationId, INACTIVE_ADMISSION);
        this.#identityByConversationId.delete(normalizedConversationId);
    }

    clear(conversationId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        this.#admissionByConversationId.delete(normalizedConversationId);
        this.#identityByConversationId.delete(normalizedConversationId);
    }

    clearAll(): void {
        this.#admissionByConversationId.clear();
        this.#identityByConversationId.clear();
    }

    get(conversationId: string | null): ChatStreamAdmissionStatus {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return INACTIVE_ADMISSION;
        }
        return this.#admissionByConversationId.get(normalizedConversationId) ?? INACTIVE_ADMISSION;
    }

    getIdentity(conversationId: string | null): ChatTurnAdmissionStreamIdentity | null {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return null;
        }
        const identity = this.#identityByConversationId.get(normalizedConversationId) ?? null;
        if (identity === null) {
            return null;
        }
        return {
            requestId: identity.requestId,
            assistantTimestamp: identity.assistantTimestamp,
            assistantTurnTimestamp: identity.assistantTurnTimestamp,
            modelVariantIndex: identity.modelVariantIndex
        };
    }
}

export { ChatStreamAdmissionState };
