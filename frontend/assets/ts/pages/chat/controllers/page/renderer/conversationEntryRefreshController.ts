/* SoAI - Chat page conversation entry refresh controller [frontend/assets/ts/pages/chat/controllers/page/renderer/conversationEntryRefreshController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasSettledAssistantActionsChrome } from '@features/chat/public.ts';

type ConversationEntryRefreshDecision = 'skip' | 'skip-dom-streaming' | 'refresh';

const hasStaleIdleStreamingAssistantDom = (inputArguments: { isActiveStreamingMessageEntry: boolean; node: HTMLElement }): boolean => {
    if (inputArguments.isActiveStreamingMessageEntry || !inputArguments.node.classList.contains('assistant')) {
        return false;
    }
    return !hasSettledAssistantActionsChrome(inputArguments.node);
};

const decideConversationEntryDomRefresh = (inputArguments: { previousSignature: string | null; nextSignature: string; isCurrentStreaming: boolean; isActiveStreamingMessageEntry: boolean; node: HTMLElement }): ConversationEntryRefreshDecision => {
    if (hasStaleIdleStreamingAssistantDom({ isActiveStreamingMessageEntry: inputArguments.isActiveStreamingMessageEntry, node: inputArguments.node })) {
        return 'refresh';
    }
    if (inputArguments.previousSignature === inputArguments.nextSignature) {
        return 'skip';
    }
    if (inputArguments.isCurrentStreaming && inputArguments.isActiveStreamingMessageEntry && inputArguments.node.classList.contains('assistant')) {
        return 'skip-dom-streaming';
    }
    return 'refresh';
};

const shouldAnimateInsertedConversationEntry = (isCurrentStreaming: boolean): boolean => {
    if (!isCurrentStreaming) {
        return true;
    }
    return false;
};

export { decideConversationEntryDomRefresh, hasStaleIdleStreamingAssistantDom, shouldAnimateInsertedConversationEntry };
export type { ConversationEntryRefreshDecision };
