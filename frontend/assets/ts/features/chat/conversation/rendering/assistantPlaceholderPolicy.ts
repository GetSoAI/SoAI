/* SoAI - Chat feature assistant placeholder policy [frontend/assets/ts/features/chat/conversation/rendering/assistantPlaceholderPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEmptyAssistantPlaceholderMessage } from '@features/chat/message/placeholderAssistantMessage.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';

const resolveLastNonSystemMessageIndex = (messages: readonly ChatMessage[]): number => {
    if (messages.length === 0) {
        return -1;
    }
    for (let index = messages.length - 1; index >= 0; index -= 1) {
        const candidate = messages[index];
        if (!candidate) {
            continue;
        }
        if (candidate.role === 'system') {
            continue;
        }
        return index;
    }
    return -1;
};

const shouldRenderAssistantPlaceholder = (message: ChatMessage, index: number, inputArguments: { isCurrentStreaming: boolean; lastNonSystemIndex: number }): boolean => {
    if (!isEmptyAssistantPlaceholderMessage(message)) {
        return true;
    }
    if (inputArguments.isCurrentStreaming && index === inputArguments.lastNonSystemIndex) {
        return true;
    }
    return false;
};

export { resolveLastNonSystemMessageIndex, shouldRenderAssistantPlaceholder };
