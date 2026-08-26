/* SoAI - Retained tool timeline retention policy [frontend/assets/ts/features/chat/chatstreamservice/retainedToolTimelineRetention.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasRetainableSubagentTool } from '@features/chat/chatstreamservice/retainedToolTimelineSession.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const canRetainOwnerSession = (conversationId: string, session: ChatStreamSession): boolean => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    return Boolean(normalizedConversationId && hasRetainableSubagentTool(session));
};

export { canRetainOwnerSession, hasRetainableSubagentTool };
