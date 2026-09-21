/* SoAI - Chat message runtime operation contracts [frontend/assets/ts/features/chat/message/runtimeOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentShellToolStopResponse } from '@core/api/contracts/chatAgentContracts.ts';
import type { ConversationExecutionRunResult } from '@core/chat/protocols.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatStreamResponseOptions } from '@features/chat/chatstreamservice/types.ts';
import type { ChatStorageMessageRecord, LoadConversationMessagesOptions } from '@features/chat/storage/storageModels.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface RemoveCompactionBoundaryRequest {
    conversationId: string;
    assistantTurnAtMs: number;
    modelVariantIndex: number;
    toolCallId: string;
    expectedLastModifiedAtMs: number;
}

interface StopShellRequest {
    conversationId: string;
    assistantTurnAtMs: number;
    modelVariantIndex: number;
    toolCallId: string;
}

interface ChatMessageRuntimeOperations {
    saveAndSync: (conversation: ConversationContract) => Promise<void>;
    resubmitUserMessage: (conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number; message: ChatStorageMessageRecord }) => Promise<void>;
    deleteMessageByCursor: (conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number }) => Promise<void>;
    loadConversationMessages: (conversationId: string, options?: LoadConversationMessagesOptions) => Promise<void>;
    refreshRunningActivitySnapshot: (conversationId: string) => Promise<void>;
    streamResponse: (conversation: ConversationContract, options?: ChatStreamResponseOptions) => Promise<void>;
    commitPendingDeletesForConversation: (conversation: ConversationContract) => Promise<void>;
    runConversationExecutionIfIdle: (conversationId: string, task: () => Promise<void>) => Promise<ConversationExecutionRunResult>;
    invalidateChatMarkup: (scope: 'current' | 'list' | 'both') => void;
    renderCurrentConversation: () => Promise<void>;
    renderConversationList: () => Promise<void>;
    refreshConversationsUI: () => Promise<void>;
    regenerateCompactionInCurrentConversation: (assistantTurnAtMs: number) => Promise<void>;
    removeCompactionBoundary: (payload: RemoveCompactionBoundaryRequest) => Promise<void>;
    stopShell: (payload: StopShellRequest) => Promise<AgentShellToolStopResponse>;
    isConversationExecuting: (conversationId: string) => boolean;
    isChatStreamingConversation: (conversationId: string) => boolean;
    reportRequestFailure: (error: Error) => void;
    regenerateConversation: (conversationId: string, payload: { expectedLastModifiedAtMs: number; target: { createdAtMs: number; messageId: number }; contentPreviewFeedback: JsonObject | null; previewContractFeedback: JsonObject | null }) => Promise<void>;
    updateConversationModel: (conversationId: string, modelId: string) => Promise<void>;
    speakText: (text: string, options?: { onPlaybackStart?: (() => void) | null }) => Promise<void>;
    stopSpeaking: () => void;
}

export type { ChatMessageRuntimeOperations, RemoveCompactionBoundaryRequest, StopShellRequest };
