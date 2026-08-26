/* SoAI - Agent render message hydration coordinator [frontend/assets/ts/pages/chat/controllers/chatpageagent/AgentRenderHydrationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';

class AgentRenderHydrationController {
    readonly #host: ChatPageAgentHost;
    readonly #completedRequestKeys = new Set<string>();
    readonly #pendingRequestKeys = new Set<string>();
    readonly #isDisposed: () => boolean;

    constructor(inputArguments: { host: ChatPageAgentHost; isDisposed: () => boolean }) {
        this.#host = inputArguments.host;
        this.#isDisposed = inputArguments.isDisposed;
    }

    request(conversationId: string, requestKey: string): void {
        const hydrationKey = `${conversationId}:${requestKey}`;
        if (this.#pendingRequestKeys.has(hydrationKey) || this.#completedRequestKeys.has(hydrationKey)) {
            return;
        }
        this.#pendingRequestKeys.add(hydrationKey);
        const activation = this.#host.conversation.captureConversationActivationSnapshot();
        void this.#hydrateAndTrack(conversationId, activation, hydrationKey).catch((error): void => {
            if (this.#isDisposed()) {
                return;
            }
            if (!this.#host.conversation.isConversationActivationSnapshotCurrent(activation, conversationId)) {
                return;
            }
            this.#host.workflow.logWarning('Failed to hydrate conversation messages for agent render', ensureError(error));
        });
    }

    clear(): void {
        this.#completedRequestKeys.clear();
        this.#pendingRequestKeys.clear();
    }

    async #hydrateAndTrack(conversationId: string, activation: ReturnType<ChatPageAgentHost['conversation']['captureConversationActivationSnapshot']>, hydrationKey: string): Promise<void> {
        try {
            await this.#hydrate(conversationId, activation, hydrationKey);
        } finally {
            this.#pendingRequestKeys.delete(hydrationKey);
        }
    }

    async #hydrate(conversationId: string, activation: ReturnType<ChatPageAgentHost['conversation']['captureConversationActivationSnapshot']>, hydrationKey: string): Promise<void> {
        await this.#host.conversation.loadConversationMessages(conversationId, { force: true });
        if (this.#isDisposed()) {
            return;
        }
        if (!this.#host.conversation.isConversationActivationSnapshotCurrent(activation, conversationId)) {
            return;
        }
        this.#host.rendering.invalidateChatMarkup('current');
        await this.#host.rendering.rerenderCurrentConversation();
        this.#completedRequestKeys.add(hydrationKey);
    }
}

export { AgentRenderHydrationController };
