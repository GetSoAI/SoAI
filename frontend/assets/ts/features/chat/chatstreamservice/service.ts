/* SoAI - Chat feature stream service [frontend/assets/ts/features/chat/chatstreamservice/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_STREAM_SERVICE_ID } from '@core/chat/protocols.ts';
import type { ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { ChatStreamConversationTitleResolution, type ConversationTitleResolver } from '@features/chat/chatstreamservice/conversationTitleResolution.ts';
import type { ChatPresentationInterests, ChatPresentationState, StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { ChatStreamOwnerDispatch } from '@features/chat/chatstreamservice/ownerDispatch.ts';
import type { PendingStopRequest } from '@features/chat/chatstreamservice/pendingStopRequests.ts';
import { StreamRequestDispositionRegistry } from '@features/chat/chatstreamservice/streamRequestDispositionRegistry.ts';
import { RetainedToolTimelineCoordinator } from '@features/chat/chatstreamservice/retainedToolTimelineCoordinator.ts';
import { ChatStreamNotificationQueue } from '@features/chat/chatstreamservice/streamNotificationQueue.ts';
import { ChatStreamTerminalNotificationCoordinator } from '@features/chat/chatstreamservice/terminalNotificationCoordinator.ts';
import { createChatStreamRuntime } from '@features/chat/chatstreamservice/streamRuntimeNotifications.ts';
import { disposeChatStreamServiceState } from '@features/chat/chatstreamservice/serviceDisposal.ts';
import { stopChatStreamSession } from '@features/chat/chatstreamservice/serviceStop.ts';
import { startChatStreamSession } from '@features/chat/chatstreamservice/serviceStart.ts';
import { interruptChatStreamSession } from '@features/chat/chatstreamservice/streamInterrupt.ts';
import { ChatStreamServiceLifecycle } from '@features/chat/chatstreamservice/serviceLifecycle.ts';
import { subscribeToChatStreamUpdates } from '@features/chat/chatstreamservice/serviceSubscription.ts';
import { ChatStreamActiveStatusSyncRunner } from '@features/chat/chatstreamservice/activeStatusSyncRunner.ts';
import { ChatStreamAdmissionState } from '@features/chat/chatstreamservice/admissionState.ts';
import type { ChatStreamMessageSavedReconciliation } from '@features/chat/chatstreamservice/messageSavedReconciliation.ts';
import type { ChatStreamLifecycle, ChatStreamSession, ChatStreamStartOptions, ChatStreamStartOutcome, ChatTurnAdmissionStreamIdentity, InterruptedStreamSnapshot, StreamListener, StreamTransportMode, StreamUpdate } from '@features/chat/chatstreamservice/types.ts';
import { ChatStreamPresentationSession } from '@features/chat/chatstreamservice/presentationSession.ts';
import { ChatStreamWebSocketControlLifecycle } from '@features/chat/chatstreamservice/websocketControlLifecycle.ts';
import { resolveActiveStreamingSession } from '@features/chat/chatstreamservice/activeStreamingSession.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

class ChatStreamService {
    readonly #apiClient: ChatStreamApiClient;
    #sessions = new Map<string, ChatStreamSession>();
    #retainedToolTimeline: RetainedToolTimelineCoordinator;
    #listeners = new Set<StreamListener>();
    #pendingStopRequests = new Map<string, PendingStopRequest>();
    #requestDispositions = new StreamRequestDispositionRegistry();
    #ownerDispatch = new ChatStreamOwnerDispatch();
    #conversationTitles = new ChatStreamConversationTitleResolution();
    #admissionState = new ChatStreamAdmissionState();
    #lifecycle = new ChatStreamServiceLifecycle();
    #notificationQueue = new ChatStreamNotificationQueue({
        sessions: this.#sessions,
        listeners: this.#listeners
    });
    #terminalNotifications = new ChatStreamTerminalNotificationCoordinator();
    #activeStatusSyncRunner: ChatStreamActiveStatusSyncRunner;
    #presentationSession: ChatStreamPresentationSession;
    #webSocketControl: ChatStreamWebSocketControlLifecycle;
    #runtime: StreamRuntime = createChatStreamRuntime({
        requestDispositions: this.#requestDispositions,
        notificationQueue: this.#notificationQueue,
        conversationTitles: this.#conversationTitles,
        admissionState: this.#admissionState,
        terminalNotifications: this.#terminalNotifications
    });

    constructor(inputArguments: { apiClient: ChatStreamApiClient; presentationInterests: ChatPresentationInterests }) {
        this.#apiClient = inputArguments.apiClient;
        this.#retainedToolTimeline = new RetainedToolTimelineCoordinator({
            apiClient: this.#apiClient,
            sessions: this.#sessions,
            runtime: this.#runtime
        });
        this.#activeStatusSyncRunner = new ChatStreamActiveStatusSyncRunner({
            apiClient: this.#apiClient,
            sessions: this.#sessions,
            runtime: this.#runtime,
            notificationQueue: this.#notificationQueue,
            retainedToolTimeline: this.#retainedToolTimeline,
            ownerDispatch: this.#ownerDispatch,
            requestDispositions: this.#requestDispositions,
            admissionState: this.#admissionState
        });
        this.#presentationSession = new ChatStreamPresentationSession({
            apiClient: this.#apiClient,
            sessions: this.#sessions,
            runtime: this.#runtime,
            retainedToolTimeline: this.#retainedToolTimeline,
            ownerDispatch: this.#ownerDispatch,
            requestDispositions: this.#requestDispositions,
            activeStatusSyncRunner: this.#activeStatusSyncRunner,
            presentationInterests: inputArguments.presentationInterests
        });
        this.#webSocketControl = new ChatStreamWebSocketControlLifecycle({
            ownerDispatch: this.#ownerDispatch,
            requestDispositions: this.#requestDispositions,
            handleFollowerCommandError: (envelope) => this.#presentationSession.handleCommandError(envelope),
            handleConnected: async () => await this.#presentationSession.handleConnected()
        });
    }

    initialize(): void {
        if (!this.#lifecycle.initialize()) {
            return;
        }
        try {
            this.#webSocketControl.initialize();
        } catch (error) {
            this.#lifecycle.dispose();
            this.#webSocketControl.dispose();
            this.#presentationSession.dispose();
            this.#activeStatusSyncRunner.dispose();
            this.#notificationQueue.dispose();
            throw error;
        }
    }

    setConversationTitleResolver(resolver: ConversationTitleResolver): () => void {
        this.#lifecycle.requireActive('set conversation title resolver');
        return this.#conversationTitles.setResolver(resolver);
    }

    registerTerminalRenderAcknowledger(): () => void {
        this.#lifecycle.requireActive('register terminal render acknowledger');
        return this.#terminalNotifications.registerRenderAcknowledger();
    }

    acquirePresentation(): () => void {
        this.#lifecycle.requireActive('acquire presentation');
        return this.#presentationSession.acquirePresentation();
    }

    setPresentationState(state: ChatPresentationState): void {
        this.#lifecycle.requireActive('set presentation state');
        this.#presentationSession.setPresentationState(state);
    }

    acknowledgeTerminalRenderSettled(conversationId: string, requestId: string | null): void {
        this.#terminalNotifications.acknowledgeRenderSettled(conversationId, requestId);
    }

    dispose(): void {
        if (!this.#lifecycle.dispose()) {
            return;
        }
        this.#webSocketControl.dispose();
        this.#presentationSession.dispose();
        this.#activeStatusSyncRunner.dispose();
        this.#notificationQueue.dispose();
        this.#terminalNotifications.dispose();
        disposeChatStreamServiceState({
            sessions: this.#sessions,
            retainedToolTimeline: this.#retainedToolTimeline,
            pendingStopRequests: this.#pendingStopRequests,
            requestDispositions: this.#requestDispositions,
            ownerDispatch: this.#ownerDispatch,
            conversationTitles: this.#conversationTitles
        });
        this.#admissionState.clearAll();
    }

    subscribe(listener: StreamListener): () => void {
        this.#lifecycle.requireActive('subscribe');
        return subscribeToChatStreamUpdates({
            listener,
            listeners: this.#listeners,
            sessions: this.#sessions,
            notificationQueue: this.#notificationQueue
        });
    }

    isStreaming(conversationId: string | null | undefined): boolean {
        return resolveActiveStreamingSession(this.#sessions, conversationId) !== null;
    }

    replayActiveStream(conversationId: string): void {
        const session = resolveActiveStreamingSession(this.#sessions, conversationId);
        if (session === null) {
            return;
        }
        this.#runtime.notify(session, { type: 'replay' });
    }

    canQueueConversationInput(conversationId: string | null): boolean {
        return this.#admissionState.get(conversationId).canAcceptConversationInput;
    }

    canSteerConversationInput(conversationId: string | null): boolean {
        return this.#admissionState.get(conversationId).canAcceptSteerPrompt;
    }

    canStartPromptNow(conversationId: string | null): boolean {
        return this.#admissionState.get(conversationId).canStartNextPrompt;
    }

    getStreamLifecycle(conversationId: string | null): ChatStreamLifecycle {
        return this.#admissionState.get(conversationId).streamLifecycle;
    }

    getStreamIdentity(conversationId: string | null): ChatTurnAdmissionStreamIdentity | null {
        return this.#admissionState.getIdentity(conversationId);
    }

    getStreamTransportMode(conversationId: string): StreamTransportMode | null {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return null;
        }
        const session = this.#sessions.get(normalizedConversationId);
        return session?.active === true ? session.transportMode : null;
    }

    getActiveAssistantMessage(conversationId: string): ChatMessage | null {
        return resolveActiveStreamingSession(this.#sessions, conversationId)?.assistantMessage ?? null;
    }

    isRequestSuppressed(conversationId: string, requestId: string): boolean {
        return this.#requestDispositions.isRequestSuppressed(conversationId, requestId);
    }

    shouldIgnorePassiveStreamEvent(conversationId: string, requestId: string): boolean {
        return this.#requestDispositions.shouldIgnorePassiveStreamEvent(conversationId, requestId);
    }

    async syncConversationStatus(conversationId: string): Promise<ChatStreamMessageSavedReconciliation> {
        this.#lifecycle.requireActive('sync conversation status');
        return await this.#syncConversationStatusIfActive(conversationId, this.#lifecycle.generation());
    }

    async syncSelectedConversationStatus(conversationId: string): Promise<void> {
        this.#lifecycle.requireActive('sync selected conversation status');
        await this.#presentationSession.syncSelectedConversationStatus(conversationId);
    }

    async reconcileMessageSaved(conversationId: string): Promise<ChatStreamMessageSavedReconciliation> {
        this.#lifecycle.requireActive('reconcile message saved');
        return await this.#syncConversationStatusIfActive(conversationId, this.#lifecycle.generation());
    }

    async #syncConversationStatusIfActive(conversationId: string, lifecycleGeneration: number): Promise<ChatStreamMessageSavedReconciliation> {
        return await this.#activeStatusSyncRunner.syncConversation({
            conversationId,
            context: 'service',
            generation: lifecycleGeneration,
            followerSessions: this.#presentationSession,
            isCurrent: (generation: number): boolean => this.#lifecycle.isGenerationActive(generation)
        });
    }

    async start(options: ChatStreamStartOptions): Promise<ChatStreamStartOutcome> {
        this.#lifecycle.requireActive('start');
        const lifecycleGeneration = this.#lifecycle.generation();
        return startChatStreamSession({
            apiClient: this.#apiClient,
            sessions: this.#sessions,
            pendingStopRequests: this.#pendingStopRequests,
            requestDispositions: this.#requestDispositions,
            ownerDispatch: this.#ownerDispatch,
            notificationQueue: this.#notificationQueue,
            retainedToolTimeline: this.#retainedToolTimeline,
            followerSessions: this.#presentationSession,
            runtime: this.#runtime,
            options,
            admissionState: this.#admissionState,
            isCurrent: () => this.#lifecycle.isGenerationActive(lifecycleGeneration),
            syncActiveStatusAfterOwnerRelease: async (conversationIdToSync: string): Promise<void> => {
                await this.#syncConversationStatusIfActive(conversationIdToSync, lifecycleGeneration);
            }
        });
    }

    stop(input: { conversationId: string; reason?: string; requestId?: string; force?: boolean; forcePendingSteers?: boolean }): void {
        this.#lifecycle.requireActive('stop');
        stopChatStreamSession({
            sessions: this.#sessions,
            pendingStopRequests: this.#pendingStopRequests,
            requestDispositions: this.#requestDispositions,
            conversationId: input.conversationId,
            ...(input.reason === undefined ? {} : { reason: input.reason }),
            ...(input.requestId === undefined ? {} : { requestId: input.requestId }),
            ...(input.force === undefined ? {} : { force: input.force }),
            ...(input.forcePendingSteers === undefined ? {} : { forcePendingSteers: input.forcePendingSteers })
        });
    }

    interrupt(input: { conversationId: string; requestId?: string | null; reason?: string | null }): InterruptedStreamSnapshot | null {
        this.#lifecycle.requireActive('interrupt');
        return interruptChatStreamSession({
            sessions: this.#sessions,
            requestDispositions: this.#requestDispositions,
            notificationQueue: this.#notificationQueue,
            runtime: this.#runtime,
            ownerDispatch: this.#ownerDispatch,
            retainedToolTimeline: this.#retainedToolTimeline,
            wsBridge: this.#presentationSession,
            conversationId: input.conversationId,
            ...(input.requestId === undefined ? {} : { requestId: input.requestId }),
            ...(input.reason === undefined ? {} : { reason: input.reason })
        });
    }
}

export { ChatStreamService, CHAT_STREAM_SERVICE_ID };
export type { StreamListener, StreamUpdate };
