/* SoAI - Chat feature message contracts [frontend/assets/ts/features/chat/message/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentCanonicalPlan } from '@core/chat/agentTypes.ts';
import type { JsonApiClient } from '@core/api/jsonRequestGate.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ChatToolIconServiceContract } from '@core/chat/protocols.ts';
import type { ChatContent, ChatMessage, ConversationContract, ConversationMessage } from '@features/chat/ChatTypes.ts';
import type { ChatKnowledgeAttachmentsApi, ChatSoaiPathsApi } from '@features/chat/pagecontracts/types.ts';
import type { ChatMessageRenderModel } from '@features/chat/message/messageRenderModel.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import type { ChatMessageRuntimeOperations } from '@features/chat/message/runtimeOperations.ts';
import type { ConversationRunningActivitySnapshot } from '@features/chat/storage/storageModels.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';
import type { ChatTurnAdmissionStreamIdentity } from '@features/chat/chatstreamservice/types.ts';

interface ChatMessageBoundaryPort {
    apiClient: JsonApiClient;
    knowledgeAttachmentsApi: Pick<ChatKnowledgeAttachmentsApi, 'items' | 'previewItem' | 'useItems' | 'delete'>;
    soaiPathsApi: Pick<ChatSoaiPathsApi, 'preview' | 'read' | 'download' | 'open' | 'token'>;
}

interface ChatMessagePresentationPort {
    sanitizer: SanitizerApi;
    chatToolIconService: ChatToolIconServiceContract;
    getCachedIcon: (name: IconName, options?: IconOptions) => TrustedHtml;
    getMessageSenderLabel: (source: ConversationMessage, defaultRole: string) => string;
    getModelTypeLabel: (modelId: string | null) => string | null;
    isThinkingFeatureEnabled: () => boolean;
    isRichTextEnabled: () => boolean;
    isCodeRecognitionEnabled: () => boolean;
    isInlineMultimediaPreviewsEnabled: () => boolean;
    isShowActivitiesEnabled: () => boolean;
    getActivityDurationDisplayMode: () => ChatActivityDurationDisplayMode;
    dom: { getDocument: () => Document };
    getAssistantAvatarUrl: () => string | null;
    getUserAvatarUrl: () => string | null;
}

interface ChatMessageSessionPort {
    getCanonicalPlan: () => AgentCanonicalPlan | null;
    getCurrentModel: () => string | null;
    getModelStreamHasPayload: () => boolean;
    isModelAvailable: (modelId: string) => boolean;
    isTerminalRenderPending: (conversationId: string, message: ChatMessage) => boolean;
    isConversationExecuting: (conversationId: string) => boolean;
    getActiveComparisonRun: (conversationId: string) => { assistantTurnTimestamp: number; variantCount: number } | null;
    getActiveStreamIdentity: (conversationId: string) => ChatTurnAdmissionStreamIdentity | null;
    getCurrentConversation: () => ConversationContract | null;
    getCurrentRunningActivitySnapshot: () => ConversationRunningActivitySnapshot | null;
    resolveConversationById: (conversationId: string) => ConversationContract | null;
}

interface ChatMessageRenderingPort {
    getAttachmentDraftRevision: () => number;
    getWorkerRenderEpoch: () => number;
    updateConversationRenderCache?: (conversationId: string, messageDomId: string, signature: string) => void;
    revealActivityElement: (element: HTMLElement) => void;
}

interface ChatMessageInteractionPort {
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    handleError: (error: Error, context: string, options?: { notify?: boolean; severity?: 'debug' | 'info' | 'warn' | 'error'; rethrow?: boolean }) => void;
    hasClipboardSupport: () => boolean;
    copyToClipboard: (text: string, options?: { notify?: (message: string, type: NotificationType) => void }) => Promise<void>;
    showNotification: (message: string, type: NotificationType) => void;
    onKnowledgeAttachmentChanged: (summary: KnowledgeAttachmentSummary) => void;
    notifyConversationContentCommitted: () => void;
}

interface ChatMessageManagerDependencies {
    runtime: ChatMessageRuntimeOperations;
    boundary: ChatMessageBoundaryPort;
    presentation: ChatMessagePresentationPort;
    session: ChatMessageSessionPort;
    rendering: ChatMessageRenderingPort;
    interaction: ChatMessageInteractionPort;
}

type ChatPostRenderRequestType = 'initialConversation' | 'canonicalFull' | 'full' | 'streamingText' | 'streamingTimeline' | 'terminal';
type ChatPostRenderCommit = () => void;
type ChatPostRenderContainerKey = {
    readonly conversationId: string | null;
    readonly epoch: number;
};
type ChatQueuedPostRenderMode = 'initialConversation' | 'canonicalFull' | 'full' | 'terminal';

export type { ChatMessageBoundaryPort, ChatMessageInteractionPort, ChatMessageManagerDependencies, ChatMessagePresentationPort, ChatMessageRenderingPort, ChatMessageSessionPort };
export type { ChatContent, ChatMessage, ChatMessageRenderModel, ChatPostRenderCommit, ChatPostRenderContainerKey, ChatPostRenderRequestType, ChatQueuedPostRenderMode, ConversationContract, ConversationMessage, MessageSegment, IconName, IconOptions };
