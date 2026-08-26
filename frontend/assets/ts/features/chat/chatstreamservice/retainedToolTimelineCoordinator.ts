/* SoAI - Chat feature retained tool timeline coordinator [frontend/assets/ts/features/chat/chatstreamservice/retainedToolTimelineCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import { createChatStreamEventPump, type SequenceMismatchDecision, type SequenceMismatchPolicy } from '@features/chat/chatstreamservice/streamRunSessionEventPump.ts';
import { buildChatStreamIdentityKey, requireChatStreamIdentityFromEnvelope, requireChatStreamIdentityFromSession, type ChatStreamIdentityKey } from '@features/chat/chatstreamservice/streamIdentity.ts';
import { RetainedToolTimelineHydrator } from '@features/chat/chatstreamservice/retainedToolTimelineHydrator.ts';
import { createRetainedToolTimelineSession } from '@features/chat/chatstreamservice/retainedToolTimelineSession.ts';
import { canRetainOwnerSession, hasRetainableSubagentTool } from '@features/chat/chatstreamservice/retainedToolTimelineRetention.ts';
import { RetainedToolTimelineRegistry, type RetainedToolTimelinePump } from '@features/chat/chatstreamservice/RetainedToolTimelineRegistry.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type SessionMap = Map<string, ChatStreamSession>;

interface PassiveFollowerDisposalHost {
    disposeConversation(convId: string): void;
}

class RetainedToolTimelineCoordinator {
    readonly #sessions: SessionMap;
    readonly #runtime: StreamRuntime;
    readonly #hydrator: RetainedToolTimelineHydrator;
    readonly #registry = new RetainedToolTimelineRegistry();
    #disposed: boolean;

    constructor(inputArguments: { apiClient: ChatStreamApiClient; sessions: SessionMap; runtime: StreamRuntime }) {
        this.#sessions = inputArguments.sessions;
        this.#runtime = inputArguments.runtime;
        this.#hydrator = new RetainedToolTimelineHydrator({ apiClient: inputArguments.apiClient, runtime: inputArguments.runtime });
        this.#disposed = false;
    }

    dispose(): void {
        this.#disposed = true;
        this.#registry.clear();
        this.#hydrator.dispose();
    }

    maybeRetainOwnerSession(conversationId: string, session: ChatStreamSession): boolean {
        if (this.#disposed) {
            return false;
        }
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return false;
        }
        if (!canRetainOwnerSession(conversationId, session)) {
            return false;
        }
        const key = buildChatStreamIdentityKey(requireChatStreamIdentityFromSession(normalizedConversationId, session));
        if (this.#registry.has(key)) {
            return true;
        }

        const retainedSession = createRetainedToolTimelineSession(session);
        const pump = createChatStreamEventPump({
            session: retainedSession,
            runtime: this.#runtime,
            failProtocol: (message: string, errorCode: string | null | undefined = null, errorPayload: JsonValue | null = null): void => {
                errorHandler.warn('ChatStreamService', 'Retained chat stream protocol error', {
                    convId: normalizedConversationId,
                    message,
                    code: errorCode ?? null,
                    payload: errorPayload ?? null
                });
            },
            markDone: (): void => undefined,
            isDone: () => !this.#registry.has(key),
            onMatchedStreamEvent: () => undefined,
            markThrowAfterFinally: () => undefined,
            sequenceMismatchPolicy: this.#createRetainedMismatchPolicy(key, normalizedConversationId, retainedSession)
        });
        this.#registry.retain(normalizedConversationId, key, retainedSession, pump);
        return true;
    }

    async maybeRetainOwnerSessionAfterHydration(conversationId: string, session: ChatStreamSession): Promise<boolean> {
        if (this.#disposed) {
            return false;
        }
        if (this.maybeRetainOwnerSession(conversationId, session)) {
            return true;
        }
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return false;
        }
        const key = buildChatStreamIdentityKey(requireChatStreamIdentityFromSession(normalizedConversationId, session));
        try {
            await this.#hydrator.hydrateStreamState(key, normalizedConversationId, session, () => session.status === 'streaming');
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('ChatStreamService', 'Retained stream hydration failed during retain attempt', {
                convId: normalizedConversationId,
                error: runtimeError
            });
            return false;
        }
        if (this.#disposed) {
            return false;
        }
        return this.maybeRetainOwnerSession(normalizedConversationId, session);
    }

    dispatchRetainedStreamEvent(envelope: ChatStreamEventEnvelope): boolean {
        if (this.#disposed) {
            return false;
        }
        const key = buildChatStreamIdentityKey(requireChatStreamIdentityFromEnvelope(envelope));
        const eventType = envelope.eventType.trim();
        if (!eventType.startsWith('tool_call_')) {
            return false;
        }
        const session = this.#registry.getSession(key);
        if (!session) {
            return false;
        }
        const pump = this.#registry.getPump(key);
        if (!pump) {
            return false;
        }
        pump.handleStreamEnvelope(envelope);
        this.#deleteRetainedAfterDrain(key, session, pump);
        return true;
    }

    maybeDisposePassiveFollowerSession(convId: string, followerCoordinator: PassiveFollowerDisposalHost | null): void {
        if (this.#disposed) {
            return;
        }
        if (!followerCoordinator) {
            return;
        }
        const normalizedConvId = normalizeConversationId(convId);
        if (!normalizedConvId) {
            return;
        }
        const session = this.#sessions.get(normalizedConvId);
        if (!session || session.transportMode !== 'follower' || session.status !== 'streaming') {
            return;
        }
        if (session.countsAsStreaming) {
            return;
        }
        if (hasRetainableSubagentTool(session)) {
            return;
        }
        followerCoordinator.disposeConversation(normalizedConvId);
    }

    clearConversation(convId: string): void {
        if (this.#disposed) {
            return;
        }
        const normalizedConvId = normalizeConversationId(convId);
        if (!normalizedConvId) {
            return;
        }
        this.#registry.clearConversation(normalizedConvId);
    }

    clearRequest(convId: string, requestId: string): void {
        if (this.#disposed) {
            return;
        }
        const normalizedConvId = normalizeConversationId(convId);
        const normalizedRequestId = typeof requestId === 'string' ? requestId.trim() : '';
        if (!normalizedConvId || !normalizedRequestId) {
            return;
        }
        this.#registry.clearRequest(normalizedConvId, normalizedRequestId);
    }

    #createRetainedMismatchPolicy(key: ChatStreamIdentityKey, convId: string, session: ChatStreamSession): SequenceMismatchPolicy {
        return {
            decide: ({ receivedSequence }): SequenceMismatchDecision => {
                const normalizedConvId = normalizeConversationId(convId);
                const required = Number.isInteger(receivedSequence) && receivedSequence >= 0 ? receivedSequence : 0;
                terminateHandledPromise(this.#hydrateRetainedGap(key, normalizedConvId, session, required));
                return { action: 'pause' };
            }
        };
    }

    async #hydrateRetainedGap(key: ChatStreamIdentityKey, convId: string, session: ChatStreamSession, requiredSequence: number): Promise<void> {
        if (this.#disposed) {
            return;
        }
        try {
            await this.#hydrator.hydrateStreamStateUntilSequence(key, convId, session, requiredSequence, () => this.#registry.hasSession(key, session));
        } catch (error) {
            if (this.#disposed) {
                return;
            }
            const runtimeError = ensureError(error);
            errorHandler.warn('ChatStreamService', 'Retained stream hydration failed', { convId: convId, error: runtimeError });
            this.#registry.delete(key);
            return;
        }
        if (this.#disposed) {
            return;
        }
        const pump = this.#registry.getPump(key);
        if (!pump) {
            return;
        }
        pump.resume();
        this.#deleteRetainedAfterDrain(key, session, pump);
    }

    #deleteRetainedAfterDrain(key: ChatStreamIdentityKey, session: ChatStreamSession, pump: RetainedToolTimelinePump): void {
        void pump
            .waitForQueuedStreamEvents()
            .then(() => {
                if (!this.#registry.hasSession(key, session)) {
                    return;
                }
                if (!hasRetainableSubagentTool(session)) {
                    this.#registry.delete(key);
                }
            })
            .catch((error) => {
                if (this.#disposed) {
                    return;
                }
                const runtimeError = ensureError(error);
                errorHandler.warn('ChatStreamService', 'Retained stream drain failed', { convId: session.conversationId, error: runtimeError });
                this.#registry.delete(key);
            });
    }
}

export { RetainedToolTimelineCoordinator };
export type { PassiveFollowerDisposalHost };
