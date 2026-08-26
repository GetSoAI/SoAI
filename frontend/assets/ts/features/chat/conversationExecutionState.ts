/* SoAI - Canonical chat conversation execution-state policy [frontend/assets/ts/features/chat/conversationExecutionState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ConversationExecutionStatus = 'idle' | 'chat_streaming' | 'agent_running';

type ConversationExecutionState = {
    executionStatus: ConversationExecutionStatus;
    isExecuting: boolean;
    isChatStreaming: boolean;
};

type ConversationExecutionStateInput = {
    activeChatConversationIds: ReadonlySet<string>;
    conversationId: string;
    isStreamingConversation: (conversationId: string) => boolean;
    isAgentRenderingActive: (conversationId: string) => boolean;
};

const resolveConversationChatStreaming = (inputArguments: Omit<ConversationExecutionStateInput, 'isAgentRenderingActive'>): boolean => {
    return inputArguments.activeChatConversationIds.has(inputArguments.conversationId) || inputArguments.isStreamingConversation(inputArguments.conversationId);
};

const resolveConversationExecutionState = (inputArguments: ConversationExecutionStateInput): ConversationExecutionState => {
    if (resolveConversationChatStreaming(inputArguments)) {
        return { executionStatus: 'chat_streaming', isExecuting: true, isChatStreaming: true };
    }
    if (inputArguments.isAgentRenderingActive(inputArguments.conversationId)) {
        return { executionStatus: 'agent_running', isExecuting: true, isChatStreaming: false };
    }
    return { executionStatus: 'idle', isExecuting: false, isChatStreaming: false };
};

export { resolveConversationChatStreaming, resolveConversationExecutionState };
export type { ConversationExecutionState, ConversationExecutionStatus };
