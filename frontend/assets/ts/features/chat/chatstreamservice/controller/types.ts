/* SoAI - Chat feature controller contracts [frontend/assets/ts/features/chat/chatstreamservice/controller/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DeferredRejectionReason } from '@core/runtime/deferred.ts';
import type { AgentTurnCancelRequest, AgentTurnCancelResponse } from '@core/api/contracts/chatAgentContracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ChatParameters, Conversation, LoadConversationMessagesOptions } from '@features/chat/storage/storageModels.ts';
import type { ConversationIdleWaiterState } from '@features/chat/chatstreamservice/controller/idleWaiters.ts';
import type { ChatStreamLifecycle, ChatStreamResponseOptions, ChatStreamStartOptions, ChatStreamStartOutcome, ChatTurnAdmissionStreamIdentity, InterruptedStreamSnapshot, StreamTransportMode, StreamUpdate } from '@features/chat/chatstreamservice/types.ts';
import type { StreamingElementCache } from '@features/chat/stream/streamDomCache.ts';
import type { StreamMessageManager } from '@features/chat/stream/streamMessageRenderingContracts.ts';
import type { StreamRenderPatchType, StreamRenderSnapshot, StreamTextAppend } from '@features/chat/stream/streamRenderPatchType.ts';
import type { ComparisonTurnPreflightResult } from '@features/chat/comparisonTurnPreflight.ts';
import type { ChatStreamMessageSavedReconciliation } from '@features/chat/chatstreamservice/messageSavedReconciliation.ts';
import type { AssistantMessageRenderPort } from '@features/chat/message/assistantMessageDomPatch.ts';

interface ChatStreamingUiManager {
    isAutoScrollEnabled(): boolean;
    shouldAutoScrollAfterContentUpdate(): boolean;
    setAutoScrollEnabled(enabled: boolean): void;
    scrollToBottom(): void;
    applyExecutionControls(): void;
}

type ScheduledStreamRenderHandler = ((render: PendingRender) => void) & {
    drop: (message: ChatMessage, conversationId: string) => boolean;
    cancel: () => void;
};

interface ChatStreamingMessageManager extends StreamMessageManager, AssistantMessageRenderPort {
    invalidateMessageCache(message: ChatMessage | null | undefined): void;
    resolveRunningActivityRefreshDelayMs(message: ChatMessage, nowMs: number): number | null;
}

interface ChatStreamingStorageManager {
    loadConversationMessages(conversationId: string, options?: LoadConversationMessagesOptions): Promise<void>;
    saveAndSync(conversation: ConversationContract, options?: { force?: boolean; sync?: boolean; messageSyncMode?: 'replace' | 'append_tail' }): Promise<void>;
}

interface ChatStreamServiceInterface {
    subscribe(listener: (update: StreamUpdate) => Promise<void> | void): () => void;
    setConversationTitleResolver(resolveConversationTitle: (conversationId: string) => string | null): () => void;
    isStreaming(conversationId: string | null | undefined): boolean;
    canQueueConversationInput(conversationId: string | null): boolean;
    canSteerConversationInput(conversationId: string | null): boolean;
    canStartPromptNow(conversationId: string | null): boolean;
    getStreamLifecycle(conversationId: string | null): ChatStreamLifecycle;
    getStreamIdentity(conversationId: string | null): ChatTurnAdmissionStreamIdentity | null;
    getStreamTransportMode(conversationId: string): StreamTransportMode | null;
    syncConversationStatus(conversationId: string): Promise<ChatStreamMessageSavedReconciliation>;
    syncSelectedConversationStatus(conversationId: string): Promise<void>;
    replayActiveStream(conversationId: string): void;
    start(options: ChatStreamStartOptions): Promise<ChatStreamStartOutcome>;
    stop(options: { conversationId: string; reason?: string; requestId?: string; force?: boolean; forcePendingSteers?: boolean }): void;
    interrupt(options: { conversationId: string; requestId?: string | null; reason?: string | null }): InterruptedStreamSnapshot | null;
    isRequestSuppressed(conversationId: string, requestId: string): boolean;
}

export interface ChatStreamingControllerState {
    getCurrentConversationId(): string | null;
    getCurrentModel(): string | null;
}

interface ChatStreamingPresentationPort {
    optionalUI(selector: string, parent?: Element): Element | null;
    updateHTML(element: Element, html: TrustedHtml | string, options?: { escape?: boolean }): void;
    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void;
    renderCurrentConversation(): Promise<void>;
    renderConversationList(): Promise<void>;
    onTerminalPostRenderCommitted?(conversationId: string, requestId: string | null): void;
    updateConversationRenderCache?(conversationId: string, messageDomId: string, signature: string): void;
}

export interface ChatStreamTerminalUpdate {
    conversationId: string;
    requestId: string | null;
    assistantTimestamp: number;
    status: 'complete' | 'error' | 'cancelled';
    conversationListRenderAlreadyScheduled: boolean;
}

export interface ChatStreamingControllerDependencies {
    cancelAgentTurn?: (conversationId: string, turnId: string, options: AgentTurnCancelRequest) => Promise<AgentTurnCancelResponse>;
    uiManager: ChatStreamingUiManager;
    messageManager: ChatStreamingMessageManager;
    storageManager: ChatStreamingStorageManager;
    chatStreamService: ChatStreamServiceInterface;
    preflightComparisonTurn(inputArguments: { conversationId: string; primaryModelId: string; comparisonModelIds: string[]; minimumAssistantTurnAtMs?: number | null }): Promise<ComparisonTurnPreflightResult>;
    conversations: Map<string, Conversation>;
    state: ChatStreamingControllerState;
    getModelStreamHasPayload: () => boolean;
    isModelAvailable: (modelId: string) => boolean;
    onStreamTerminalUpdate?: (update: ChatStreamTerminalUpdate) => void;
    onStreamingStateChange?: (conversationId: string, isStreaming: boolean) => void;
    presentation: ChatStreamingPresentationPort;
    reportRequestFailure(error: Error): void;
    getRequestParameters(): JsonObject;
    getWorkingParameters(): ChatParameters;
    resolveAgentModeForConversation?(conversationId: string): 'chat' | 'plan' | 'execute';
    resolveAgentRunningTurnId?(conversationId: string): string | null;
    isAgentRenderingActive?(conversationId: string): boolean;
    createStreamRenderRuntime(context: ChatStreamingControllerContext): ChatStreamRenderRuntime;
}

export interface ChatStreamRenderRuntime {
    scheduleStreamRender: ScheduledStreamRenderHandler;
    reconcileActivityDurations: (root: Element, conversationId: string) => void;
}

interface StreamErrorHandler {
    debug?: (scope: string, message: string, error?: Error) => void;
    error?: (scope: string, message: string, error?: Error) => void;
}

export interface ChatStreamingControllerOptions {
    errorHandler?: StreamErrorHandler | null;
}

export interface PendingRender {
    message: ChatMessage;
    conversationId: string;
    patchType: StreamRenderPatchType;
    assistantRevision: number | null;
    textAppend: StreamTextAppend | null;
}

export type StreamLifecyclePhase = 'idle' | 'starting' | 'streaming' | 'stopping' | 'terminalizing';

export interface ComparisonRunState {
    groupRequestId: string;
    assistantTurnTimestamp: number;
    variantCount: number;
    aborting: boolean;
}

export interface ConversationStreamState {
    phase: StreamLifecyclePhase;
    updatedAtMs: number;
    requestToken: number;
    requestId: string | null;
    assistantTimestamp: number | null;
    currentConversationMountPending: boolean;
    currentConversationMountQueued: boolean;
    currentConversationMountPromise: Promise<void> | null;
    comparisonRun: ComparisonRunState | null;
    streamRenderSnapshot: StreamRenderSnapshot | null;
    terminalizationKey: string | null;
    terminalizationPromiseKey: string | null;
    terminalizationPromise: Promise<void> | null;
    terminalizationResolve: (() => void) | null;
    terminalizationReject: ((error: DeferredRejectionReason) => void) | null;
    terminalRenderToken: number;
    terminalRenderTimerId: number | null;
    terminalRenderSettled: boolean;
    activityRefreshTimerId: number | null;
}

export interface ChatStreamingControllerContext {
    dependencies: ChatStreamingControllerDependencies;
    errorHandler: StreamErrorHandler | null;
    scheduleStreamRender: ScheduledStreamRenderHandler | null;
    reconcileActivityDurations: ((root: Element, conversationId: string) => void) | null;
    missingTargetRecoveryConversationId: string | null;
    isRenderInProgress: boolean;
    serviceUnsubscribe: (() => void) | null;
    cachedStreamingElements: StreamingElementCache | null;
    streamStateByConversationId: Map<string, ConversationStreamState>;
    idleWaitersByConversationId: ConversationIdleWaiterState;
    requestTokenByConversationId: Map<string, number>;
    timers: ResourceTracker;
    presentationActive: boolean;
    presentationGeneration: number;
    disposed: boolean;
}

export type { ChatStreamResponseOptions, StreamUpdate };
