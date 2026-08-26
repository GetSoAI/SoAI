/* SoAI - Shared helpers for resolving MCP elicitation prompts from the chat page UI [frontend/assets/ts/pages/chat/controllers/chatpage/construction/elicitation/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeConversationId } from '@features/chat/public.ts';

type NormalizedResolutionIds = {
    conversationId: string;
    taskId: string;
};

const CHAT_VALIDATION_NOTIFICATION_DURATION_MS = 4500;

const normalizeResolutionIds = (conversationId: string, taskId: string): NormalizedResolutionIds | null => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    const normalizedTaskId = taskId.trim();
    if (!normalizedConversationId || !normalizedTaskId) {
        return null;
    }
    return { conversationId: normalizedConversationId, taskId: normalizedTaskId };
};

export { CHAT_VALIDATION_NOTIFICATION_DURATION_MS, normalizeResolutionIds };
export type { NormalizedResolutionIds };
