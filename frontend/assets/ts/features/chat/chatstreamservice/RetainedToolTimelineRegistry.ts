/* SoAI - Retained tool timeline registry [frontend/assets/ts/features/chat/chatstreamservice/RetainedToolTimelineRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import type { createChatStreamEventPump } from '@features/chat/chatstreamservice/streamRunSessionEventPump.ts';
import type { ChatStreamIdentityKey } from '@features/chat/chatstreamservice/streamIdentity.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type RetainedToolTimelinePump = ReturnType<typeof createChatStreamEventPump>;

class RetainedToolTimelineRegistry {
    readonly #pumpsByKey = new Map<ChatStreamIdentityKey, RetainedToolTimelinePump>();
    readonly #sessionsByKey = new Map<ChatStreamIdentityKey, ChatStreamSession>();
    readonly #keysByConversation = new Map<string, Set<ChatStreamIdentityKey>>();

    clear(): void {
        this.#pumpsByKey.clear();
        this.#sessionsByKey.clear();
        this.#keysByConversation.clear();
    }

    has(key: ChatStreamIdentityKey): boolean {
        return this.#pumpsByKey.has(key);
    }

    hasSession(key: ChatStreamIdentityKey, session: ChatStreamSession): boolean {
        return this.#sessionsByKey.get(key) === session;
    }

    getSession(key: ChatStreamIdentityKey): ChatStreamSession | null {
        return this.#sessionsByKey.get(key) ?? null;
    }

    getPump(key: ChatStreamIdentityKey): RetainedToolTimelinePump | null {
        return this.#pumpsByKey.get(key) ?? null;
    }

    retain(conversationId: string, key: ChatStreamIdentityKey, session: ChatStreamSession, pump: RetainedToolTimelinePump): void {
        this.#pumpsByKey.set(key, pump);
        this.#sessionsByKey.set(key, session);
        const keys = this.#keysByConversation.get(conversationId) ?? new Set<ChatStreamIdentityKey>();
        keys.add(key);
        this.#keysByConversation.set(conversationId, keys);
    }

    delete(key: ChatStreamIdentityKey): void {
        const session = this.getSession(key);
        if (session) {
            this.#deleteConversationKey(session.conversationId, key);
        }
        this.#pumpsByKey.delete(key);
        this.#sessionsByKey.delete(key);
    }

    clearConversation(conversationId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        const keys = this.#keysByConversation.get(normalizedConversationId);
        if (keys) {
            for (const key of Array.from(keys.values())) {
                this.delete(key);
            }
        }
        this.#keysByConversation.delete(normalizedConversationId);
    }

    clearRequest(conversationId: string, requestId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const normalizedRequestId = typeof requestId === 'string' ? requestId.trim() : '';
        if (!normalizedConversationId || !normalizedRequestId) {
            return;
        }
        const keys = this.#keysByConversation.get(normalizedConversationId);
        if (!keys) {
            return;
        }
        for (const key of Array.from(keys.values())) {
            const session = this.getSession(key);
            if (session && session.requestId.trim() === normalizedRequestId) {
                this.delete(key);
            }
        }
    }

    #deleteConversationKey(conversationId: string, key: ChatStreamIdentityKey): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        const keys = this.#keysByConversation.get(normalizedConversationId);
        if (!keys) {
            return;
        }
        keys.delete(key);
        if (!keys.size) {
            this.#keysByConversation.delete(normalizedConversationId);
        }
    }
}

export { RetainedToolTimelineRegistry };
export type { RetainedToolTimelinePump };
