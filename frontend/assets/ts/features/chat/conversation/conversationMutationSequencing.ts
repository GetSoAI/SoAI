/* SoAI - Chat feature conversation mutation sequencing [frontend/assets/ts/features/chat/conversation/conversationMutationSequencing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ConversationMutationType = 'archived' | 'color' | 'favorite' | 'title';

class ConversationMutationSequencer {
    #versionsByKey: Map<string, number> = new Map();

    begin(conversationId: string, type: ConversationMutationType): number {
        const key = this.#buildKey(conversationId, type);
        const nextVersion = (this.#versionsByKey.get(key) ?? 0) + 1;
        this.#versionsByKey.set(key, nextVersion);
        return nextVersion;
    }

    isCurrent(conversationId: string, type: ConversationMutationType, version: number): boolean {
        return this.#versionsByKey.get(this.#buildKey(conversationId, type)) === version;
    }

    clearConversation(conversationId: string): void {
        for (const key of this.#versionsByKey.keys()) {
            if (key.startsWith(`${conversationId}:`)) {
                this.#versionsByKey.delete(key);
            }
        }
    }

    #buildKey(conversationId: string, type: ConversationMutationType): string {
        return `${conversationId}:${type}`;
    }
}

export { ConversationMutationSequencer };
export type { ConversationMutationType };
