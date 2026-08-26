/* SoAI - Selected chat presentation session [frontend/assets/ts/features/chat/chatstreamservice/presentationSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { createActiveStatusReconciliationLoop, type ActiveStatusReconciliationLoop } from '@features/chat/chatstreamservice/activeStatusReconciliationLoop.ts';
import { ChatStreamFollowerCoordinator } from '@features/chat/chatstreamservice/followerCoordinator.ts';
import type { ChatStreamStatusPreviewEventEnvelope } from '@core/realtime/eventcontracts/chatStreamStatusPreview.ts';
import type { ChatPresentationInterests, ChatPresentationState, StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamSession, HydratedSnapshotApplicationResult } from '@features/chat/chatstreamservice/types.ts';
import type { ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import type { RetainedToolTimelineCoordinator } from '@features/chat/chatstreamservice/retainedToolTimelineCoordinator.ts';
import type { ChatStreamOwnerDispatch } from '@features/chat/chatstreamservice/ownerDispatch.ts';
import type { StreamRequestDispositionRegistry } from '@features/chat/chatstreamservice/streamRequestDispositionRegistry.ts';
import { isSuppressedStreamEvent } from '@features/chat/chatstreamservice/websocketBridgeSuppression.ts';
import { dispatchChatStreamStatusPreview } from '@features/chat/chatstreamservice/streamStatusPreviewDispatch.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import { markChatStreamOwnerReleaseRequested } from '@features/chat/chatstreamservice/streamOwnerRelease.ts';
import { resolveComparisonGroupRequestId } from '@features/chat/chatstreamservice/comparisonRequestIdentity.ts';
import { ChatStreamActiveStatusSyncRunner } from '@features/chat/chatstreamservice/activeStatusSyncRunner.ts';

const log = createModuleLogger('ChatStreamPresentationSession', { defaultLevel: 'warn' });

type ChatStreamPresentationSessionOptions = {
    apiClient: ChatStreamApiClient;
    sessions: Map<string, ChatStreamSession>;
    runtime: StreamRuntime;
    retainedToolTimeline: RetainedToolTimelineCoordinator;
    ownerDispatch: ChatStreamOwnerDispatch;
    requestDispositions: StreamRequestDispositionRegistry;
    activeStatusSyncRunner: ChatStreamActiveStatusSyncRunner;
    presentationInterests: ChatPresentationInterests;
};

class ChatStreamPresentationSession {
    readonly #apiClient: ChatStreamApiClient;
    readonly #sessions: Map<string, ChatStreamSession>;
    readonly #runtime: StreamRuntime;
    readonly #retainedToolTimeline: RetainedToolTimelineCoordinator;
    readonly #ownerDispatch: ChatStreamOwnerDispatch;
    readonly #requestDispositions: StreamRequestDispositionRegistry;
    readonly #activeStatusSyncRunner: ChatStreamActiveStatusSyncRunner;
    readonly #presentationInterests: ChatStreamPresentationSessionOptions['presentationInterests'];
    readonly #activeStatusReconciliation: ActiveStatusReconciliationLoop;
    #followerCoordinator: ChatStreamFollowerCoordinator | null = null;
    #presentationUnsubscribe: (() => void) | null = null;
    #presentationInterestToken: string | null = null;
    #selectedConversationId: string | null = null;
    #presentationVisible = false;
    #syncGeneration: number = 0;

    constructor(options: ChatStreamPresentationSessionOptions) {
        this.#apiClient = options.apiClient;
        this.#sessions = options.sessions;
        this.#runtime = options.runtime;
        this.#retainedToolTimeline = options.retainedToolTimeline;
        this.#ownerDispatch = options.ownerDispatch;
        this.#requestDispositions = options.requestDispositions;
        this.#activeStatusSyncRunner = options.activeStatusSyncRunner;
        this.#presentationInterests = options.presentationInterests;
        this.#activeStatusReconciliation = createActiveStatusReconciliationLoop({
            sessions: this.#sessions,
            activeStatusSyncRunner: this.#activeStatusSyncRunner,
            syncGeneration: () => this.#syncGeneration,
            selectedConversationId: () => this.#selectedConversationId,
            followerSessions: this,
            isActive: () => this.#presentationUnsubscribe !== null && this.#presentationInterestToken !== null,
            isSyncCurrent: (generation) => this.#isSyncCurrent(generation),
            logWarning: (message, error) => log('warn', message, error)
        });
    }

    acquirePresentation(): () => void {
        if (this.#presentationUnsubscribe !== null) {
            throw new Error('Chat stream presentation is already active');
        }
        this.#syncGeneration += 1;
        try {
            this.#ensureFollowerCoordinator();
            this.#presentationUnsubscribe = subscribeManagedWebSocketContracts({
                label: 'ChatStreamPresentationSession',
                events: [
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.chatStream.timeline,
                        handler: (envelope) => this.#handleTimelineEvent(envelope)
                    }),
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.chatStream.statusPreview,
                        handler: (envelope) => this.#handleStatusPreviewEvent(envelope)
                    })
                ]
            });
            if (this.#presentationVisible && this.#selectedConversationId !== null) {
                this.#presentationInterestToken = this.#presentationInterests.acquireChatPresentationInterest(this.#selectedConversationId);
                if (this.#presentationInterestToken === null) {
                    throw new Error('Chat presentation interest acquisition failed');
                }
            }
        } catch (error) {
            this.dispose();
            throw error;
        }
        terminateHandledPromise(this.handleConnected());
        let released = false;
        return (): void => {
            if (released) {
                return;
            }
            released = true;
            this.dispose();
        };
    }

    setPresentationState(state: ChatPresentationState): void {
        const normalizedConversationId = normalizeConversationId(state.conversationId) || null;
        const presentationVisible = state.visible && normalizedConversationId !== null;
        const selectionChanged = normalizedConversationId !== this.#selectedConversationId;
        if (!selectionChanged && presentationVisible === this.#presentationVisible) {
            return;
        }
        const previousConversationId = this.#selectedConversationId;
        this.#selectedConversationId = normalizedConversationId;
        this.#presentationVisible = presentationVisible;
        this.#syncGeneration += 1;
        this.#activeStatusReconciliation.stop(selectionChanged ? 'chat-stream-presentation-selection-changed' : 'chat-stream-presentation-visibility-changed');
        if (selectionChanged && previousConversationId !== null) {
            this.#activeStatusSyncRunner.cancelPresentationSync(previousConversationId);
            this.#followerCoordinator?.disposeConversation(previousConversationId);
            this.#releaseUnselectedOwner(previousConversationId);
        } else if (!presentationVisible && previousConversationId !== null) {
            this.#activeStatusSyncRunner.cancelPresentationSync(previousConversationId);
            this.#releaseUnselectedOwner(previousConversationId);
        }
        if (this.#presentationUnsubscribe === null) {
            return;
        }
        if (!presentationVisible || normalizedConversationId === null) {
            const interestToken = this.#presentationInterestToken;
            this.#presentationInterestToken = null;
            if (interestToken !== null) this.#presentationInterests.releaseInterest(interestToken);
            if (normalizedConversationId === null) {
                this.#followerCoordinator?.dispose();
                this.#followerCoordinator = null;
            }
            return;
        }
        this.#ensureFollowerCoordinator();
        if (this.#presentationInterestToken === null) {
            this.#presentationInterestToken = this.#presentationInterests.acquireChatPresentationInterest(normalizedConversationId);
            if (this.#presentationInterestToken === null) {
                throw new Error('Chat presentation interest acquisition failed');
            }
        } else {
            this.#presentationInterests.updateChatPresentationInterest(this.#presentationInterestToken, normalizedConversationId);
        }
        const session = this.#sessions.get(normalizedConversationId);
        if (session?.active && session.status === 'streaming' && session.countsAsStreaming) {
            this.#runtime.notify(session, { type: 'replay' });
        }
        terminateHandledPromise(this.handleConnected());
    }

    #isSyncCurrent(syncGeneration: number): boolean {
        return this.#presentationUnsubscribe !== null && this.#presentationVisible && this.#syncGeneration === syncGeneration;
    }

    disposeFollowerConversation(conversationId: string): void {
        this.#followerCoordinator?.disposeConversation(conversationId);
    }

    disposeFollowerRequest(conversationId: string, requestId: string): void {
        this.#followerCoordinator?.disposeRequest(conversationId, requestId);
    }

    async applyFollowerSnapshot(conversationId: string, requestId: string, assistantMessage: ChatMessage, notifyUserOnTerminal: boolean): Promise<HydratedSnapshotApplicationResult | null> {
        return (await this.#followerCoordinator?.applySnapshot(conversationId, requestId, assistantMessage, notifyUserOnTerminal)) ?? null;
    }

    syncActiveStatusReconciliation(): void {
        this.#activeStatusReconciliation.sync();
    }

    async handleConnected(): Promise<void> {
        if (this.#presentationUnsubscribe === null || !this.#presentationVisible || this.#selectedConversationId === null) {
            return;
        }
        if (await this.#syncSelectedConversation()) this.syncActiveStatusReconciliation();
    }

    async syncSelectedConversationStatus(conversationId: string): Promise<boolean> {
        if (normalizeConversationId(conversationId) !== this.#selectedConversationId) return false;
        return await this.#syncSelectedConversation();
    }

    handleCommandError(envelope: Parameters<ChatStreamFollowerCoordinator['handleCommandErrorEvent']>[0]): void {
        this.#followerCoordinator?.handleCommandErrorEvent(envelope);
    }

    async #syncSelectedConversation(): Promise<boolean> {
        const conversationId = this.#selectedConversationId;
        const presentationInterestToken = this.#presentationInterestToken;
        if (conversationId === null || presentationInterestToken === null) return false;
        const bridgeGeneration = this.#syncGeneration;
        try {
            await this.#presentationInterests.waitForChatPresentationInterest(presentationInterestToken, conversationId);
            if (!this.#isSyncCurrent(bridgeGeneration)) return false;
            await this.#activeStatusSyncRunner.syncConversation({
                conversationId,
                context: 'presentation',
                generation: bridgeGeneration,
                followerSessions: this,
                isCurrent: (generation: number): boolean => generation === bridgeGeneration && this.#isSyncCurrent(generation)
            });
            return this.#isSyncCurrent(bridgeGeneration);
        } catch (error) {
            if (isLifecycleCancellationError(error)) {
                log('debug', 'Selected conversation status sync superseded', ensureError(error));
            } else {
                log('warn', 'Selected conversation status sync failed', ensureError(error));
            }
        }
        return false;
    }

    #requestConversationReconcile(conversationId: string): void {
        if (this.#presentationUnsubscribe === null || this.#presentationInterestToken === null || normalizeConversationId(conversationId) !== this.#selectedConversationId) {
            return;
        }
        const bridgeGeneration = this.#syncGeneration;
        void this.#activeStatusSyncRunner
            .syncConversation({
                conversationId,
                context: 'presentation',
                generation: bridgeGeneration,
                followerSessions: this,
                isCurrent: (generation: number): boolean => generation === bridgeGeneration && this.#isSyncCurrent(generation)
            })
            .then(() => this.syncActiveStatusReconciliation())
            .catch((error) => {
                log('warn', 'Active stream status sync after hydration exhaustion failed', ensureError(error));
            });
    }

    #handleStatusPreviewEvent(envelope: ChatStreamStatusPreviewEventEnvelope): void {
        if (this.#presentationUnsubscribe === null || this.#presentationInterestToken === null || normalizeConversationId(envelope.convId) !== this.#selectedConversationId) {
            return;
        }
        dispatchChatStreamStatusPreview({
            envelope,
            sessions: this.#sessions,
            runtime: this.#runtime,
            requestDispositions: this.#requestDispositions
        });
    }

    #handleTimelineEvent(envelope: ChatStreamEventEnvelope): void {
        if (this.#presentationUnsubscribe === null || this.#presentationInterestToken === null || normalizeConversationId(envelope.convId) !== this.#selectedConversationId) {
            return;
        }
        if (isSuppressedStreamEvent(this.#requestDispositions, envelope, 'owner')) {
            return;
        }
        if (this.#ownerDispatch.dispatchStreamEvent(envelope)) {
            return;
        }
        if (isSuppressedStreamEvent(this.#requestDispositions, envelope, 'passive')) {
            return;
        }
        if (this.#retainedToolTimeline.dispatchRetainedStreamEvent(envelope)) {
            return;
        }
        this.#followerCoordinator?.handleStreamEvent(envelope);
        this.#activeStatusReconciliation.sync();
        this.#retainedToolTimeline.maybeDisposePassiveFollowerSession(normalizeConversationId(envelope.convId), this.#followerCoordinator);
    }

    dispose(): void {
        this.#syncGeneration += 1;
        this.#activeStatusReconciliation.stop('chat-stream-presentation-hidden');
        this.#presentationUnsubscribe?.();
        this.#presentationUnsubscribe = null;
        const presentationInterestToken = this.#presentationInterestToken;
        this.#presentationInterestToken = null;
        this.#followerCoordinator?.dispose();
        this.#followerCoordinator = null;
        if (presentationInterestToken !== null) {
            this.#presentationInterests.releaseInterest(presentationInterestToken);
        }
    }

    #releaseUnselectedOwner(conversationId: string): void {
        const session = this.#sessions.get(conversationId);
        if (session?.active !== true || session.transportMode !== 'owner') return;
        if (resolveComparisonGroupRequestId(session.requestId) !== session.requestId) return;
        markChatStreamOwnerReleaseRequested(session);
    }

    #ensureFollowerCoordinator(): void {
        if (this.#followerCoordinator !== null) return;
        this.#followerCoordinator = new ChatStreamFollowerCoordinator({
            apiClient: this.#apiClient,
            sessions: this.#sessions,
            runtime: this.#runtime,
            shouldIgnoreEvent: (conversationId: string, requestId: string): boolean => this.#requestDispositions.shouldIgnorePassiveStreamEvent(conversationId, requestId),
            requestReconcile: (conversationId: string): void => this.#requestConversationReconcile(conversationId)
        });
    }
}

export { ChatStreamPresentationSession };
