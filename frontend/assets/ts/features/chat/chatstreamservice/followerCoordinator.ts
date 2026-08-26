/* SoAI - Chat feature follower coordinator [frontend/assets/ts/features/chat/chatstreamservice/followerCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamSession, HydratedSnapshotApplicationResult } from '@features/chat/chatstreamservice/types.ts';
import { finalizeChatStreamProtocolFailure } from '@features/chat/chatstreamservice/streamTerminalizationPolicy.ts';
import { createChatStreamEventPump, type SequenceMismatchPolicy } from '@features/chat/chatstreamservice/streamRunSessionEventPump.ts';
import type { ChatStreamCommandErrorEnvelope } from '@core/realtime/eventcontracts/chatStreamCommandError.ts';
import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import { ChatStreamHydrationSession, buildDefaultFetchStreamState, type FetchStreamState } from '@features/chat/chatstreamservice/streamHydrationSession.ts';
import { requestFollowerHydrationRecovery, type FollowerRecoveryReconcileRequest } from '@features/chat/chatstreamservice/followerHydrationRecovery.ts';
import { ensureFollowerSessionForEnvelope } from '@features/chat/chatstreamservice/followerSessionResolution.ts';
import type { ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import { buildChatStreamIdentityKey, compareChatStreamIdentityToSession, requireChatStreamIdentityFromEnvelope, requireChatStreamIdentityFromSession, type ChatStreamIdentityKey } from '@features/chat/chatstreamservice/streamIdentity.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type Sleep = (ms: number) => Promise<void>;
type ShouldIgnoreEvent = (convId: string, requestId: string) => boolean;

class ChatStreamFollowerCoordinator {
    readonly #sessions: Map<string, ChatStreamSession>;
    readonly #runtime: StreamRuntime;
    readonly #fetchStreamState: FetchStreamState;
    readonly #sleep: Sleep | null;
    readonly #shouldIgnoreEvent: ShouldIgnoreEvent | null;
    readonly #requestReconcile: FollowerRecoveryReconcileRequest | null;
    readonly #activeKeyByConversation = new Map<string, ChatStreamIdentityKey>();
    readonly #pumpsByKey = new Map<ChatStreamIdentityKey, ReturnType<typeof createChatStreamEventPump>>();
    readonly #hydratorsByKey = new Map<ChatStreamIdentityKey, ChatStreamHydrationSession>();

    constructor(inputArguments: { apiClient: ChatStreamApiClient; sessions: Map<string, ChatStreamSession>; runtime: StreamRuntime; fetchStreamState?: FetchStreamState | null; sleep?: Sleep | null; shouldIgnoreEvent?: ShouldIgnoreEvent | null; requestReconcile?: FollowerRecoveryReconcileRequest | null }) {
        this.#sessions = inputArguments.sessions;
        this.#runtime = inputArguments.runtime;
        this.#fetchStreamState = buildDefaultFetchStreamState(inputArguments.apiClient, inputArguments.fetchStreamState ?? null);
        this.#sleep = inputArguments.sleep ?? null;
        this.#shouldIgnoreEvent = inputArguments.shouldIgnoreEvent ?? null;
        this.#requestReconcile = inputArguments.requestReconcile ?? null;
    }

    dispose(): void {
        for (const hydrator of this.#hydratorsByKey.values()) {
            hydrator.dispose();
        }
        this.#activeKeyByConversation.clear();
        this.#pumpsByKey.clear();
        this.#hydratorsByKey.clear();
    }

    disposeConversation(convId: string): void {
        const normalizedConvId = normalizeConversationId(convId);
        if (!normalizedConvId) {
            return;
        }
        const session = this.#sessions.get(normalizedConvId);
        const key = this.#activeKeyByConversation.get(normalizedConvId) ?? null;
        if (key) {
            this.#releaseFollowerSession(key, normalizedConvId, session ?? null);
            return;
        }
        if (session && session.transportMode === 'follower') {
            session.active = false;
            this.#sessions.delete(normalizedConvId);
        }
    }

    disposeRequest(convId: string, requestId: string): void {
        const normalizedConvId = normalizeConversationId(convId);
        const normalizedRequestId = toTrimmedString(requestId);
        if (!normalizedConvId || !normalizedRequestId) {
            return;
        }
        const session = this.#sessions.get(normalizedConvId);
        if (!session || session.transportMode !== 'follower' || session.requestId.trim() !== normalizedRequestId) {
            return;
        }
        this.disposeConversation(normalizedConvId);
    }

    handleStreamEvent(envelope: ChatStreamEventEnvelope): void {
        const identity = requireChatStreamIdentityFromEnvelope(envelope);
        const convId = identity.convId;
        const requestId = identity.requestId;
        if (this.#shouldIgnoreEvent?.(convId, requestId) === true) {
            return;
        }
        const existing = this.#sessions.get(convId);
        if (existing && existing.active && existing.transportMode === 'owner') {
            return;
        }
        if (existing && existing.active && existing.transportMode === 'follower') {
            const comparison = compareChatStreamIdentityToSession(identity, existing);
            if (comparison < 0) {
                return;
            }
            const matchesExisting = existing.requestId.trim() === requestId && comparison === 0;
            if (!matchesExisting) {
                if (comparison > 0) {
                    this.disposeConversation(convId);
                } else {
                    return;
                }
            }
        }
        const followerSession = this.#ensureFollowerSessionForEnvelope(envelope);
        const key = buildChatStreamIdentityKey(requireChatStreamIdentityFromSession(convId, followerSession));
        this.#activeKeyByConversation.set(convId, key);
        const pump = this.#ensureFollowerPump(key, convId, followerSession);
        pump.handleStreamEnvelope(envelope);
    }

    handleCommandErrorEvent(envelope: ChatStreamCommandErrorEnvelope): void {
        const convId = normalizeConversationId(envelope.convId);
        if (!convId) {
            return;
        }
        const requestId = toTrimmedString(envelope.requestId);
        const session = this.#sessions.get(convId);
        if (!session || !session.active || session.transportMode !== 'follower') {
            return;
        }
        if (!requestId || session.requestId.trim() !== requestId) {
            return;
        }
        const key = this.#activeKeyByConversation.get(convId) ?? null;
        if (!key) {
            return;
        }
        const pump = this.#pumpsByKey.get(key);
        if (!pump) {
            return;
        }
        pump.handleCommandErrorEnvelope(envelope);
    }

    async applySnapshot(conversationId: string, requestId: string, assistantMessage: ChatMessage, notifyUserOnTerminal: boolean): Promise<HydratedSnapshotApplicationResult | null> {
        const convId = normalizeConversationId(conversationId);
        const normalizedRequestId = toTrimmedString(requestId);
        if (!convId || !normalizedRequestId) {
            return null;
        }
        const session = this.#sessions.get(convId);
        if (!session || !session.active || session.transportMode !== 'follower' || session.requestId.trim() !== normalizedRequestId) {
            return null;
        }
        const key = this.#activeKeyByConversation.get(convId) ?? buildChatStreamIdentityKey(requireChatStreamIdentityFromSession(convId, session));
        const pump = this.#pumpsByKey.get(key);
        if (!pump) {
            return null;
        }
        return await pump.applyHydratedSnapshot(assistantMessage, { resume: true, notifyUserOnTerminal });
    }

    #ensureFollowerSessionForEnvelope(envelope: ChatStreamEventEnvelope): ChatStreamSession {
        return ensureFollowerSessionForEnvelope({
            sessions: this.#sessions,
            runtime: this.#runtime,
            envelope,
            disposeConversation: (convId: string) => this.disposeConversation(convId)
        });
    }

    #ensureFollowerPump(key: ChatStreamIdentityKey, convId: string, session: ChatStreamSession): ReturnType<typeof createChatStreamEventPump> {
        const existing = this.#pumpsByKey.get(key);
        if (existing) {
            return existing;
        }
        const failProtocol = (message: string, errorCode: string | null | undefined = null, errorPayload: JsonValue | null = null): void => {
            finalizeChatStreamProtocolFailure({
                session,
                runtime: this.#runtime,
                message,
                errorCode: optionalTrimmedString(errorCode),
                errorPayload
            });
            this.#releaseFollowerSession(key, convId, session);
        };
        const markDone = (): void => {
            this.#releaseFollowerSession(key, convId, session);
        };
        const onMatchedStreamEvent = (): void => {
            if (!session.active) {
                session.active = true;
            }
            session.status = 'streaming';
            session.countsAsStreaming = true;
        };
        const sequenceMismatchPolicy: SequenceMismatchPolicy = {
            decide: ({ receivedSequence }): { action: 'pause' } => {
                const hydration = this.#requireHydrator(key, convId, session);
                requestFollowerHydrationRecovery({
                    hydration,
                    receivedSequence,
                    convId,
                    requestReconcile: this.#requestReconcile,
                    failProtocol
                });
                return { action: 'pause' };
            }
        };
        const pump = createChatStreamEventPump({
            session,
            runtime: this.#runtime,
            failProtocol,
            markDone,
            isDone: () => !session.active || session.status !== 'streaming',
            onMatchedStreamEvent,
            markThrowAfterFinally: () => undefined,
            sequenceMismatchPolicy
        });
        this.#pumpsByKey.set(key, pump);
        this.#hydratorsByKey.set(
            key,
            new ChatStreamHydrationSession({
                convId,
                session,
                pump,
                fetchStreamState: this.#fetchStreamState,
                sleep: this.#sleep
            })
        );
        return pump;
    }

    #requireHydrator(key: ChatStreamIdentityKey, convId: string, session: ChatStreamSession): ChatStreamHydrationSession {
        const existing = this.#hydratorsByKey.get(key);
        if (existing) {
            return existing;
        }
        const pump = this.#pumpsByKey.get(key);
        if (!pump) {
            throw new Error('Follower hydrator requires an existing event pump.');
        }
        const hydrator = new ChatStreamHydrationSession({
            convId,
            session,
            pump,
            fetchStreamState: this.#fetchStreamState,
            sleep: this.#sleep
        });
        this.#hydratorsByKey.set(key, hydrator);
        return hydrator;
    }

    #releaseFollowerSession(key: ChatStreamIdentityKey, convId: string, session: ChatStreamSession | null): void {
        const normalizedConvId = normalizeConversationId(convId);
        if (normalizedConvId && this.#activeKeyByConversation.get(normalizedConvId) === key) {
            this.#activeKeyByConversation.delete(normalizedConvId);
        }
        this.#pumpsByKey.delete(key);
        const hydrator = this.#hydratorsByKey.get(key);
        if (hydrator) {
            hydrator.dispose();
            this.#hydratorsByKey.delete(key);
        }
        if (!session || session.transportMode !== 'follower') {
            return;
        }
        session.active = false;
        if (normalizedConvId && this.#sessions.get(normalizedConvId) === session) {
            this.#sessions.delete(normalizedConvId);
        }
    }
}

export { ChatStreamFollowerCoordinator };
