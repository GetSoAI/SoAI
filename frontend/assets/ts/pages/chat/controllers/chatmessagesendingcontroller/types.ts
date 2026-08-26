/* SoAI - Chat message sending controller contracts [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { ConversationExecutionRunResult } from '@core/chat/protocols.ts';
import type { ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';
import type { ChatAttachment, ChatContentSegment, ChatPageApi, ChatParameters, ChatStreamLifecycle, ChatStreamResponseOptions, ChatStreamStartAdmission, ChatStreamStopOptions, ChatTurnAdmissionSnapshot, Conversation, ConversationExportModelDescriptor, ConversationMessage, LoadConversationMessagesOptions, RagIngestionAttachmentSource, RagIngestionStatus, SoaiPathDraftRecord } from '@features/chat/public.ts';
import type { ComposerSoaiLinkResolutionManager } from '@pages/chat/controllers/chatmessagesendingcontroller/composerSoaiLinkResolutionManager.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

type Message = ConversationMessage;

type QueuedSendBlockReason = 'aborted' | 'conversation-mismatch' | 'stale' | 'streaming';

type QueuedSendGuardResult = boolean | { allowed: false; reason: QueuedSendBlockReason };

type QueuedSendGuard = (context: QueuedSendGuardContext) => QueuedSendGuardResult;

type QueuedSendOutcome = { status: 'sent' } | { status: 'aborted' } | { status: 'blocked'; reason: QueuedSendBlockReason };
type ConversationInputComposerOutcome = 'enqueued' | 'empty' | 'not-admitted' | 'stale' | 'conversation-changed';
interface SendMessageOptions {
    onEffectiveSendCommitted?: (() => void) | undefined;
}

interface StartRagIngestionArguments {
    conversationId: string;
    conversation: Conversation;
    files: File[];
    attachmentSource: RagIngestionAttachmentSource;
}

interface ChatRagAttachmentPort {
    currentStatus: () => RagIngestionStatus | null;
    statusForConversation: (conversationId: string) => RagIngestionStatus | null;
    currentKnowledgeDrafts: () => KnowledgeAttachmentSummary[];
    refreshKnowledgeDrafts: () => void;
    handleKnowledgeChanged: (summary: KnowledgeAttachmentSummary) => void;
    subscribeStatus: (handler: () => void) => () => void;
    cancelCurrent: () => Promise<void>;
    cancel: (conversationId: string) => Promise<void>;
    start: (inputArguments: StartRagIngestionArguments) => Promise<void>;
}

interface ChatMessageSendingPort {
    readonly rag: ChatRagAttachmentPort;
    hasPendingAttachmentProcessing: () => boolean;
    sendMessage: (options?: SendMessageOptions) => Promise<void>;
    sendTextMessage: (text: string, attachmentContent?: readonly ChatContentSegment[]) => Promise<void>;
    sendQueuedTextMessage: (text: string, attachmentContent: readonly ChatContentSegment[], signal: AbortSignal, beforeSend: (context: QueuedSendGuardContext) => QueuedSendGuardResult) => Promise<QueuedSendOutcome>;
    resolveSoaiLinksFromInput: (input: HTMLTextAreaElement, inputValue: string) => Promise<void>;
    runConversationExecutionIfIdle: (conversationId: string, task: () => Promise<void>) => Promise<ConversationExecutionRunResult>;
    queueConversationInputFromComposer: (intent: 'queued' | 'steer') => Promise<ConversationInputComposerOutcome>;
    steerActiveStream: () => Promise<ConversationInputComposerOutcome>;
    removeAttachedFile: (fileId: string) => Promise<void>;
    removeDraftKnowledgeAttachment: (knowledgeAttachmentId: string) => Promise<void>;
    exportConversation: (conversationId: string | null) => void;
    handleFileUpload: (event: Event) => Promise<void>;
    handleSelectedUploadFiles: (files: File[]) => Promise<void>;
    handleCameraCaptureFile: (file: File) => Promise<void>;
    handleFolderUpload: (event: Event) => Promise<void>;
    handleSelectedFolderUploadFiles: (files: File[]) => Promise<void>;
    dispose: () => void;
}

interface AttachmentManager {
    hasPendingAttachmentProcessing: () => boolean;
    getAttachments: () => ChatAttachment[];
    getDraftRevision: () => number;
    getDraftCommitEpoch: () => number;
    markDraftCommitStarted: () => void;
    subscribeDraftChanges: (listener: () => void) => () => void;
    markKnowledgeAttachmentChanged: () => void;
    waitForAttachments: (attachments?: readonly ChatAttachment[]) => Promise<void>;
    buildContentFragmentsFromAttachments: (attachments: ChatAttachment[]) => ChatContentSegment[];
    addResolvedSoaiPathRecords: (records: readonly SoaiPathDraftRecord[]) => number;
    discardSoaiPathDraftAttachments: (materializeRecord: (record: SoaiPathDraftRecord) => void) => number;
    checkoutAttachments: (attachments?: readonly ChatAttachment[]) => ChatAttachment[];
    restoreAttachments: (attachments: ChatAttachment[]) => void | Promise<void>;
    handleFiles: (files: File[], options?: { forceDocument?: boolean }) => Promise<void>;
    handleUpload: (files: File[], inputArguments: { source: 'picker' | 'camera' | 'folder'; visionSupported: boolean }) => Promise<void>;
    removeAttachedFile: (fileId: string, materializeRecord: (record: SoaiPathDraftRecord) => void) => Promise<void>;
}

interface StorageManager {
    saveState: (force?: boolean) => void;
    saveChatState: (force?: boolean) => void;
    loadConversationMessages: (conversationId: string, options?: LoadConversationMessagesOptions) => Promise<void>;
    readConversationSnapshot: (conversationId: string, signal?: AbortSignal) => Promise<Conversation>;
    saveAndSync: (conversation: Conversation | null, options?: { force?: boolean; sync?: boolean; messageSyncMode?: 'replace' | 'append_tail' }) => Promise<void>;
    resolveUserKey: () => string | null;
}

interface ChatStreamingController {
    isStreamingConversation: (conversationId: string) => boolean;
    canQueueConversationInput: (conversationId: string) => boolean;
    getStreamLifecycle: (conversationId: string) => ChatStreamLifecycle;
    streamResponse: (conversation: Conversation, options?: ChatStreamResponseOptions) => Promise<void>;
    stopStreaming: (options?: ChatStreamStopOptions) => void;
    interruptStreaming: (conversationId: string, reason?: string) => void;
    waitForConversationIdle: (conversationId: string, signal: AbortSignal) => Promise<void>;
    waitForTerminalReconciliation: (conversationId: string, signal?: AbortSignal | null) => Promise<void>;
    resolveStartAdmission: (conversationId: string, signal?: AbortSignal | null) => Promise<ChatStreamStartAdmission>;
    resolveSyncedTurnAdmission: (conversationId: string, signal?: AbortSignal | null) => Promise<ChatTurnAdmissionSnapshot>;
}

interface ConversationManager {
    isConversationPersisted: (conversationId: string) => boolean;
    ensureConversationPersisted: (conversation: Conversation) => Promise<void>;
    updateConversationSettings: (conversationId: string, patch: ConversationModelSettingsUpdate) => Promise<void>;
    updateConversationTitle: (conversationId: string, title: string) => Promise<void>;
}

interface ConversationInputsManager {
    enqueue: (conversationId: string, payload: { intent: 'queued' | 'steer'; text: string | null; sourceText: string | null; attachmentContent: readonly ChatContentSegment[] }) => Promise<{ inputId: string; acceptedAtMs: number; isDispatchableHead: boolean }>;
}

interface QueuedSendGuardContext {
    conversationId: string;
    startedFromEmptyConversation: boolean;
    createdConversationForSend: boolean;
    isFirstMessage: boolean;
    isStreaming: boolean;
}

interface MessageSendingPlatformPort extends PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    handleError: (error: Error, title: string, options?: { notify?: boolean }) => void;
    getDocument: () => Document;
    ensureManagersInitialized: (owner: ChatMessageSendingPort) => Promise<void>;
    ensureConversationForSend: () => Promise<{ conversationId: string; created: boolean } | null>;
    getRuntimeAbortSignal: () => AbortSignal | null;
    subscribeKnowledgeAttachmentChanged: (listener: (summary: KnowledgeAttachmentSummary) => void) => () => void;
}

interface MessageSendingComposerPort {
    getChatInput: () => HTMLTextAreaElement | null;
    queryDocumentUI: (selector: string) => Element[];
    setUIValue: (element: Element, value: string, options?: { attribute?: string }) => void;
    resizeChatInput: (element: Element) => void;
    noteChatInputDraftChanged: (value: string) => void;
    updateInputState: () => void;
}

interface MessageSendingPresentationPort {
    updateEmptyStateInputHint: () => void;
    refreshConversationsUI: () => Promise<void>;
    invalidateChatMarkup: (scope: 'current' | 'list' | 'both') => void;
    renderCurrentConversation: () => Promise<void>;
    flushDOMUpdates: () => void;
    renderAttachedFilesPreview: () => void;
    hideAttachedFilesPreview: () => void;
    updateExportButtonVisibility: () => void;
    shouldAutoScrollAfterContentUpdate: () => boolean;
    forceTimelineScrollToBottom: () => void;
}

interface MessageSendingConversationPort {
    getCurrentConversation: () => Conversation | null;
    getConversationById: (conversationId: string) => Conversation | null;
    isConversationExecuting: (conversationId: string) => boolean;
    commitPendingDeletesForConversation: (conversation: Conversation) => Promise<void>;
    conversations: Map<string, Conversation>;
    resolveAgentModeForConversation: (conversationId: string) => 'chat' | 'plan' | 'execute';
    waitForPendingAgentModeUpdate: () => Promise<void>;
}

interface MessageSendingModelPort {
    getCurrentModel: () => string | null;
    resolveModelDescriptor: (modelId: string) => ConversationExportModelDescriptor | null;
    isVisionSupportedForCurrentModel: () => boolean;
    getModelStreamHasPayload: () => boolean;
    isModelAvailable: (modelId: string) => boolean;
    getParameters: () => ChatParameters;
}

interface MessageSendingServicePort {
    getSoaiLinkResolutionManager: () => ComposerSoaiLinkResolutionManager;
    getAttachmentManager: () => AttachmentManager;
    getStorageManager: () => StorageManager;
    getChatStreamingController: () => ChatStreamingController;
    getConversationManager: () => ConversationManager;
    getConversationInputsManager: () => ConversationInputsManager;
    getChatApi: () => ChatPageApi;
    getChatPreferences: () => JsonValue;
    renderConversationExportMessages: (conversation: Conversation) => string;
    enhanceConversationExportInlineMedia: (container: HTMLElement, conversationId: string) => Promise<void>;
}

interface MessageSendingHost {
    platform: MessageSendingPlatformPort;
    composer: MessageSendingComposerPort;
    presentation: MessageSendingPresentationPort;
    conversation: MessageSendingConversationPort;
    model: MessageSendingModelPort;
    services: MessageSendingServicePort;
}

export type { AttachmentManager, ConversationInputsManager, StorageManager, ChatMessageSendingPort, ChatRagAttachmentPort, ChatStreamingController, ConversationManager, MessageSendingHost, ConversationInputComposerOutcome, QueuedSendBlockReason, QueuedSendGuard, QueuedSendGuardContext, QueuedSendGuardResult, QueuedSendOutcome, SendMessageOptions, StartRagIngestionArguments, ChatParameters, ChatPageApi, Conversation, Message };
