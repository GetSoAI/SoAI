/* SoAI - Active chat stream status sync runner [frontend/assets/ts/features/chat/chatstreamservice/activeStatusSyncRunner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isRequestTimeoutError } from '@core/apiError.ts';
import { isAbortError } from '@core/errors/abort.ts';
import type { ActiveStatusInactiveTransitionArguments } from '@features/chat/chatstreamservice/activeStatusInactiveTransition.ts';
import { syncChatStreamConversationStatus } from '@features/chat/chatstreamservice/activeStatusSync.ts';
import { requireCanonicalMessageLoad, type ChatStreamMessageSavedReconciliation } from '@features/chat/chatstreamservice/messageSavedReconciliation.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type ActiveStatusSyncRunnerOptions = Omit<ActiveStatusInactiveTransitionArguments, 'conversationId' | 'followerSessions' | 'isCurrent'>;

type ActiveStatusSyncRunnerRequest = {
    context: 'presentation' | 'service';
    generation: number;
    followerSessions: ActiveStatusInactiveTransitionArguments['followerSessions'];
    isCurrent: (generation: number) => boolean;
};

type ActiveStatusSyncRunnerConversationRequest = ActiveStatusSyncRunnerRequest & {
    conversationId: string;
};

type ConversationSyncEntry = {
    context: ActiveStatusSyncRunnerRequest['context'];
    generation: number;
    rerunRequested: boolean;
    abortController: AbortController;
    promise: Promise<ChatStreamMessageSavedReconciliation>;
};

class ChatStreamActiveStatusSyncRunner {
    readonly #options: ActiveStatusSyncRunnerOptions;
    readonly #sessions: Map<string, ChatStreamSession>;
    readonly #inFlightByConversationId = new Map<string, ConversationSyncEntry>();

    constructor(options: ActiveStatusSyncRunnerOptions) {
        this.#options = options;
        this.#sessions = options.sessions;
    }

    dispose(): void {
        for (const entry of this.#inFlightByConversationId.values()) entry.abortController.abort();
        this.#inFlightByConversationId.clear();
    }

    cancelPresentationSync(conversationId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) return;
        const entry = this.#inFlightByConversationId.get(normalizedConversationId);
        if (entry?.context === 'presentation') entry.abortController.abort();
    }

    async sync(request: ActiveStatusSyncRunnerRequest): Promise<void> {
        if (!request.isCurrent(request.generation)) {
            return;
        }
        const conversationIds: string[] = [];
        for (const [conversationId, session] of this.#sessions.entries()) {
            if (session.active && session.status === 'streaming' && session.countsAsStreaming) {
                conversationIds.push(conversationId);
            }
        }
        await Promise.all(conversationIds.map(async (conversationId) => await this.#requestConversation({ ...request, conversationId })));
    }

    async syncConversation(request: ActiveStatusSyncRunnerConversationRequest): Promise<ChatStreamMessageSavedReconciliation> {
        const conversationId = normalizeConversationId(request.conversationId);
        if (!conversationId || !request.isCurrent(request.generation)) {
            return requireCanonicalMessageLoad('stale-generation');
        }
        return await this.#requestConversation({ ...request, conversationId });
    }

    #requestConversation(request: ActiveStatusSyncRunnerConversationRequest): Promise<ChatStreamMessageSavedReconciliation> {
        const existing = this.#inFlightByConversationId.get(request.conversationId);
        if (existing && existing.context === request.context && existing.generation === request.generation) {
            existing.rerunRequested = true;
            return existing.promise;
        }
        existing?.abortController.abort();
        const entry = {
            context: request.context,
            generation: request.generation,
            rerunRequested: false,
            abortController: new AbortController(),
            promise: Promise.resolve(requireCanonicalMessageLoad('stale-generation'))
        } satisfies ConversationSyncEntry;
        entry.promise = this.#syncUntilSettled(request, entry).finally(() => {
            if (this.#inFlightByConversationId.get(request.conversationId) === entry) {
                this.#inFlightByConversationId.delete(request.conversationId);
            }
        });
        this.#inFlightByConversationId.set(request.conversationId, entry);
        return entry.promise;
    }

    async #syncUntilSettled(request: ActiveStatusSyncRunnerConversationRequest, entry: ConversationSyncEntry): Promise<ChatStreamMessageSavedReconciliation> {
        let result = requireCanonicalMessageLoad('stale-generation');
        do {
            entry.rerunRequested = false;
            if (!request.isCurrent(request.generation)) {
                return requireCanonicalMessageLoad('stale-generation');
            }
            try {
                result = await syncChatStreamConversationStatus({
                    ...this.#options,
                    conversationId: request.conversationId,
                    signal: entry.abortController.signal,
                    followerSessions: request.followerSessions,
                    isCurrent: () => request.isCurrent(request.generation)
                });
            } catch (error) {
                if (isAbortError(error)) {
                    return requireCanonicalMessageLoad('stale-generation');
                }
                if (isRequestTimeoutError(error)) {
                    return requireCanonicalMessageLoad('status-sync-timeout');
                }
                throw error;
            }
        } while (entry.rerunRequested && request.isCurrent(request.generation));
        return result;
    }
}

export { ChatStreamActiveStatusSyncRunner };
