/* SoAI - Per-conversation settings update serialization [frontend/assets/ts/features/chat/conversation/ConversationSettingsUpdateQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class ConversationSettingsUpdateQueue {
    #tailsByConversationId: Map<string, Promise<void>> = new Map();

    async enqueue<Result>(conversationId: string, operation: () => Promise<Result>): Promise<Result> {
        const previousTail = this.#tailsByConversationId.get(conversationId) ?? null;
        const operationPromise = (async (): Promise<Result> => {
            if (previousTail) {
                await previousTail;
            }
            return await operation();
        })();
        const trackedTail = operationPromise.then(
            (): void => {},
            (): void => {}
        );
        this.#tailsByConversationId.set(conversationId, trackedTail);
        try {
            return await operationPromise;
        } finally {
            if (this.#tailsByConversationId.get(conversationId) === trackedTail) {
                this.#tailsByConversationId.delete(conversationId);
            }
        }
    }
}

export { ConversationSettingsUpdateQueue };
