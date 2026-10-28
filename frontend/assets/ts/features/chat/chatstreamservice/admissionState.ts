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

type ChatStreamAdmissionSnapshot = Readonly<{
    admission: ChatStreamAdmissionStatus;
    identity: ChatStreamAdmissionIdentity | null;
}>;

class ChatStreamAdmissionState {
    readonly #snapshotByConversationId = new Map<string, ChatStreamAdmissionSnapshot>();

    #store(normalizedConversationId: string, admission: ChatStreamAdmissionStatus, identity: ChatStreamAdmissionIdentity | null): void {
        this.#snapshotByConversationId.set(normalizedConversationId, Object.freeze({ admission, identity }));
    }

    #setLifecycle(identity: ChatStreamAdmissionConversationIdentity, streamLifecycle: ChatStreamLifecycle): void {
        const normalizedConversationId = normalizeConversationId(identity.conversationId);
        if (!normalizedConversationId) {
            return;
        }
        const snapshot = this.#snapshotByConversationId.get(normalizedConversationId) ?? null;
        const current = snapshot?.admission ?? INACTIVE_ADMISSION;
        const currentIdentity = snapshot?.identity ?? null;
        if (streamLifecycle === 'terminalizing' && current.streamLifecycle === 'inactive' && currentIdentity === null) {
            return;
        }
        if (currentIdentity !== null) {
            const identityOrder = compareChatStreamMessageOrderIdentities(identity, currentIdentity);
            if (identityOrder < 0) {
                return;
            }
            if (identityOrder === 0 && current.streamLifecycle === 'terminalizing' && streamLifecycle === 'streaming') {
                return;
            }
            if (identityOrder === 0 && current.streamLifecycle === streamLifecycle && identity.requestId === currentIdentity.requestId) {
                return;
            }
        }
        this.#store(
            normalizedConversationId,
            {
                streamLifecycle,
                canAcceptConversationInput: streamLifecycle !== 'inactive',
                canStartNextPrompt: streamLifecycle === 'inactive',
                canAcceptSteerPrompt: streamLifecycle === 'streaming',
                activeToolCallCount: streamLifecycle === 'inactive' ? 0 : current.activeToolCallCount
            },
            identity
        );
    }

    update(status: ChatStreamStatusSnapshot): void {
        const snapshot = this.#snapshotByConversationId.get(status.conversationId) ?? null;
        if (snapshot?.admission.streamLifecycle === 'terminalizing' && status.active && status.admission.streamLifecycle === 'streaming') {
            if (snapshot.identity !== null && compareChatStreamMessageOrderIdentities(status, snapshot.identity) <= 0) {
                return;
            }
        }
        this.#store(status.conversationId, status.admission, status.active ? status : null);
    }

    markStreaming(identity: ChatStreamAdmissionConversationIdentity): void {
        this.#setLifecycle(identity, 'streaming');
    }

    markTerminalizing(identity: ChatStreamAdmissionConversationIdentity): void {
        this.#setLifecycle(identity, 'terminalizing');
    }

    markCancellationTerminal(conversationId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        this.#store(
            normalizedConversationId,
            {
                streamLifecycle: 'inactive',
                canAcceptConversationInput: true,
                canStartNextPrompt: false,
                canAcceptSteerPrompt: false,
                activeToolCallCount: 0
            },
            null
        );
    }

    markInactive(conversationId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        this.#store(normalizedConversationId, INACTIVE_ADMISSION, null);
    }

    captureSnapshot(conversationId: string): ChatStreamAdmissionSnapshot {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const snapshot = this.#snapshotByConversationId.get(normalizedConversationId) ?? null;
        if (snapshot !== null) {
            return snapshot;
        }
        const inactiveSnapshot = Object.freeze({ admission: INACTIVE_ADMISSION, identity: null });
        if (normalizedConversationId) {
            this.#snapshotByConversationId.set(normalizedConversationId, inactiveSnapshot);
        }
        return inactiveSnapshot;
    }

    isSnapshotCurrent(conversationId: string, snapshot: ChatStreamAdmissionSnapshot): boolean {
        return this.#snapshotByConversationId.get(normalizeConversationId(conversationId)) === snapshot;
    }

    clear(conversationId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        this.#snapshotByConversationId.delete(normalizedConversationId);
    }

    clearAll(): void {
        this.#snapshotByConversationId.clear();
    }

    get(conversationId: string | null): ChatStreamAdmissionStatus {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return INACTIVE_ADMISSION;
        }
        return this.#snapshotByConversationId.get(normalizedConversationId)?.admission ?? INACTIVE_ADMISSION;
    }

    getIdentity(conversationId: string | null): ChatTurnAdmissionStreamIdentity | null {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return null;
        }
        const identity = this.#snapshotByConversationId.get(normalizedConversationId)?.identity ?? null;
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
export type { ChatStreamAdmissionSnapshot };
