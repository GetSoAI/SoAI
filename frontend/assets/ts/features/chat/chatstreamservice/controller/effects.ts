/* SoAI - Chat feature controller effects [frontend/assets/ts/features/chat/chatstreamservice/controller/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNumber, isObject, isString } from '@core/typeGuards.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatStreamingControllerContext } from '@features/chat/chatstreamservice/controller/types.ts';
import { resolveConversationDisplayTitleFromConversation } from '@features/chat/conversationFormatting.ts';

export function getNextMessageTimestamp(conversation: ConversationContract): number {
    const now = serverEpochMs();
    const messages = isArray(conversation?.messages) ? conversation.messages : [];
    let maxTimestamp = 0;

    for (const message of messages) {
        if (!message || !isObject(message)) {
            continue;
        }
        const timestamp = message['timestamp'];
        if (isNumber(timestamp)) {
            maxTimestamp = Math.max(maxTimestamp, timestamp);
        }
    }

    return now > maxTimestamp ? now : maxTimestamp + 1;
}

export function resolveConversationTitle(conversation: ConversationContract): string {
    const title = resolveConversationDisplayTitleFromConversation(conversation, '');
    if (!title) {
        throw new Error('Chat stream requires a conversation title');
    }
    return title;
}

export function resolveModelId(context: ChatStreamingControllerContext): string | null {
    const modelIdValue = context.dependencies.state.getCurrentModel();
    if (!isString(modelIdValue)) {
        return null;
    }

    const trimmed = modelIdValue.trim();
    return trimmed ? trimmed : null;
}
