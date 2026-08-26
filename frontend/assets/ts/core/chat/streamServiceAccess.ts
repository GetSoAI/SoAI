/* SoAI - Kernel service accessors for chat stream/presence services [frontend/assets/ts/core/chat/streamServiceAccess.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_CONVERSATION_ATTENTION_SERVICE_ID, CHAT_PAGE_PRESENCE_SERVICE_ID, CHAT_STREAM_SERVICE_ID, type ChatConversationTerminalIndicator, type ChatStreamServiceLifecycleContract } from '@core/chat/protocols.ts';
import { isChatStreamServiceLifecycleContract } from '@core/chat/streamGuards.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

type ChatPagePresenceContract = {
    isActivelyViewingConversation: (conversationId: string | null) => boolean;
};

type ChatConversationAttentionContract = {
    initialize: () => Promise<void>;
    dispose: () => void;
    getConversationTerminalIndicator: (conversationId: string | null) => ChatConversationTerminalIndicator | null;
    getTerminalIndicatorSummary: () => ChatConversationTerminalIndicator | null;
    subscribeTerminalIndicators: (handler: () => void) => () => void;
    markCurrentSnapshotSeen: () => void;
    markConversationSeen: (conversationId: string, assistantAtMs: number) => void;
};

const isChatPagePresenceContract = <T>(value: T): value is T & ChatPagePresenceContract => {
    return isObject(value) && 'isActivelyViewingConversation' in value && isFunction(value.isActivelyViewingConversation);
};

const isChatConversationAttentionContract = <T>(value: T): value is T & ChatConversationAttentionContract => {
    return isObject(value) && 'initialize' in value && 'dispose' in value && 'getConversationTerminalIndicator' in value && 'getTerminalIndicatorSummary' in value && 'subscribeTerminalIndicators' in value && 'markCurrentSnapshotSeen' in value && 'markConversationSeen' in value && isFunction(value.initialize) && isFunction(value.dispose) && isFunction(value.getConversationTerminalIndicator) && isFunction(value.getTerminalIndicatorSummary) && isFunction(value.subscribeTerminalIndicators) && isFunction(value.markCurrentSnapshotSeen) && isFunction(value.markConversationSeen);
};

const requireChatStreamServiceLifecycle = (): ChatStreamServiceLifecycleContract => {
    const service = resolveKernelService(CHAT_STREAM_SERVICE_ID);
    if (!isChatStreamServiceLifecycleContract(service)) {
        throw new Error('ChatStreamService must expose initialize() and dispose()');
    }
    return service;
};

const requireChatPagePresence = (): ChatPagePresenceContract => {
    const service = resolveKernelService(CHAT_PAGE_PRESENCE_SERVICE_ID);
    if (!isChatPagePresenceContract(service)) {
        throw new Error('ChatPagePresenceService must expose presence contract methods');
    }
    return service;
};

const requireChatConversationAttention = (): ChatConversationAttentionContract => {
    const service = resolveKernelService(CHAT_CONVERSATION_ATTENTION_SERVICE_ID);
    if (!isChatConversationAttentionContract(service)) {
        throw new Error('ChatConversationAttentionService must expose the attention contract');
    }
    return service;
};

export { requireChatConversationAttention, requireChatPagePresence, requireChatStreamServiceLifecycle };
export type { ChatConversationAttentionContract, ChatPagePresenceContract };
