/* SoAI - Chat conversation data and message lifecycle ownership [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatConversationManager, ChatMessageManager, ChatStorageManager } from '@features/chat/public.ts';

class ChatConversationRuntime {
    #conversation: ChatConversationManager | null = null;
    #messages: ChatMessageManager | null = null;
    #storage: ChatStorageManager | null = null;

    initializeConversation(manager: ChatConversationManager): void {
        if (this.#conversation) throw new Error('Chat conversation manager is already initialized');
        this.#conversation = manager;
    }

    initializeMessages(manager: ChatMessageManager): void {
        if (this.#messages) {
            manager.dispose();
            return;
        }
        this.#messages = manager;
    }

    initializeStorage(manager: ChatStorageManager): void {
        if (this.#storage) {
            manager.dispose();
            return;
        }
        this.#storage = manager;
    }

    hasConversation(): boolean {
        return this.#conversation !== null;
    }

    hasMessages(): boolean {
        return this.#messages !== null;
    }

    hasStorage(): boolean {
        return this.#storage !== null;
    }

    optionalConversation(): ChatConversationManager | null {
        return this.#conversation;
    }

    optionalMessages(): ChatMessageManager | null {
        return this.#messages;
    }

    requireConversation(): ChatConversationManager {
        if (!this.#conversation) throw new Error('Chat conversation manager is not initialized');
        return this.#conversation;
    }

    requireMessages(): ChatMessageManager {
        if (!this.#messages) throw new Error('Chat message manager is not initialized');
        return this.#messages;
    }

    requireStorage(): ChatStorageManager {
        if (!this.#storage) throw new Error('Chat storage manager is not initialized');
        return this.#storage;
    }

    disposeMessages(): void {
        this.#messages?.dispose();
        this.#messages = null;
    }

    disposeStorage(): void {
        this.#storage?.dispose();
        this.#storage = null;
    }
}

export { ChatConversationRuntime };
export interface ChatConversationRuntimeOwner {
    conversationRuntime: ChatConversationRuntime;
}
