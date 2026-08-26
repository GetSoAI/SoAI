/* SoAI - Chat feature message delete undo conversation resolver [frontend/assets/ts/features/chat/message/messageDeleteUndoConversationResolver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

interface ChatMessageDeleteUndoConversationResolverDependencies {
    getCurrentConversation: () => ConversationContract | null;
    resolveConversationById: (conversationId: string) => ConversationContract | null;
}

class ChatMessageDeleteUndoConversationResolver {
    readonly #dependencies: ChatMessageDeleteUndoConversationResolverDependencies;
    readonly #localConversationKeyByObject: WeakMap<ConversationContract, string>;
    readonly #localConversationByKey: Map<string, ConversationContract>;
    #nextLocalConversationKeyId: number;

    constructor(dependencies: ChatMessageDeleteUndoConversationResolverDependencies) {
        this.#dependencies = dependencies;
        this.#localConversationKeyByObject = new WeakMap();
        this.#localConversationByKey = new Map();
        this.#nextLocalConversationKeyId = 1;
    }

    dispose(): void {
        this.#localConversationByKey.clear();
    }

    resolveKey(conversation: ConversationContract): string {
        const idValue = conversation.id;
        const persistedId = toTrimmedString(idValue);
        if (persistedId) {
            return `persisted:${persistedId}`;
        }
        const existing = this.#localConversationKeyByObject.get(conversation);
        if (existing) {
            return existing;
        }
        const created = `local:${String(this.#nextLocalConversationKeyId++)}`;
        this.#localConversationKeyByObject.set(conversation, created);
        this.#localConversationByKey.set(created, conversation);
        return created;
    }

    resolveConversationByKey(conversationKey: string): ConversationContract | null {
        if (conversationKey.startsWith('persisted:')) {
            const conversationId = normalizeConversationId(conversationKey.slice('persisted:'.length));
            if (!conversationId) {
                return null;
            }
            return this.#dependencies.resolveConversationById(conversationId);
        }
        if (conversationKey.startsWith('local:')) {
            return this.#localConversationByKey.get(conversationKey) ?? null;
        }
        return null;
    }

    isCurrentConversationKey(conversationKey: string): boolean {
        const current = this.#dependencies.getCurrentConversation();
        if (!current) {
            return false;
        }
        return this.resolveKey(current) === conversationKey;
    }

    releaseLocalConversationKey(conversationKey: string): void {
        if (conversationKey.startsWith('local:')) {
            const conversation = this.#localConversationByKey.get(conversationKey);
            if (conversation) {
                this.#localConversationKeyByObject.delete(conversation);
            }
            this.#localConversationByKey.delete(conversationKey);
        }
    }
}

export { ChatMessageDeleteUndoConversationResolver };
