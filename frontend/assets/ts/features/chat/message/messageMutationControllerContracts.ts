/* SoAI - Shared chat message mutation controller contracts [frontend/assets/ts/features/chat/message/messageMutationControllerContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationExecutionRunResult } from '@core/chat/protocols.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatStreamResponseOptions } from '@features/chat/chatstreamservice/types.ts';
import type { MessageReferenceResolver } from '@features/chat/message/messageReferenceResolution.ts';
import type { ChatStorageMessageRecord, LoadConversationMessagesOptions } from '@features/chat/storage/storageModels.ts';

interface ChatMessageMutationDependencies {
    getCurrentConversation: () => ConversationContract | null;
    getCurrentModel: () => string | null;
    getModelStreamHasPayload: () => boolean;
    isModelAvailable: (modelId: string) => boolean;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    saveAndSync: (conversation: ConversationContract) => Promise<void>;
    loadConversationMessages: (conversationId: string, options?: LoadConversationMessagesOptions) => Promise<void>;
    streamResponse: (conversation: ConversationContract, options?: ChatStreamResponseOptions) => Promise<void>;
    runConversationExecutionIfIdle: (conversationId: string, task: () => Promise<void>) => Promise<ConversationExecutionRunResult>;
    invalidateChatMarkup: (scope: 'current' | 'list' | 'both') => void;
    renderCurrentConversation: () => Promise<void>;
    refreshConversationsUI: () => Promise<void>;
    isConversationExecuting: (conversationId: string) => boolean;
    reportRequestFailure: (error: Error) => void;
}

interface ChatMessageEditViewPort {
    domChangeTarget: EventTarget;
    getIcon: (name: IconName, options?: IconOptions) => TrustedHtml;
    renderMessageTextContent: (message: ChatMessage) => string;
    resolveMessageContainer: (messageId: string) => HTMLElement | null;
    postRender: (container: Element | null) => void;
}

interface ChatMessageEditControllerDependencies extends ChatMessageMutationDependencies {
    view: ChatMessageEditViewPort;
    resolveMessageReference: MessageReferenceResolver;
    resubmitUserMessage: (conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number; message: ChatStorageMessageRecord }) => Promise<void>;
    commitPendingDeletesForConversation: (conversation: ConversationContract) => Promise<void>;
}

export type { ChatMessageEditControllerDependencies, ChatMessageMutationDependencies };
