/* SoAI - Chat feature routes [frontend/assets/ts/features/chat/navigation/chatRoutes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { encodeSegment } from '@core/identifiers.ts';
import { isString } from '@core/typeGuards.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const CHAT_BASE_ROUTE = 'chat';

const buildChatBaseRoute = (): 'chat' => CHAT_BASE_ROUTE;

const buildChatConversationRoute = (conversationId: string): string => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        throw new Error('Chat conversation route requires a non-empty conversation id');
    }
    return `${CHAT_BASE_ROUTE}/conversation/${encodeSegment(normalizedConversationId)}`;
};

const readConversationIdFromRouteParameters = (parameters: Record<string, string>): string | null => {
    const conversationIdValue = parameters['conversationId'];
    if (!isString(conversationIdValue)) {
        return null;
    }
    const normalizedConversationId = normalizeConversationId(conversationIdValue);
    return normalizedConversationId ? normalizedConversationId : null;
};

export { buildChatBaseRoute, buildChatConversationRoute, readConversationIdFromRouteParameters };
