/* SoAI - Chat feature active streaming session [frontend/assets/ts/features/chat/chatstreamservice/activeStreamingSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

function resolveActiveStreamingSession(sessions: ReadonlyMap<string, ChatStreamSession>, conversationId: string | null | undefined): ChatStreamSession | null {
    if (!conversationId) {
        return null;
    }
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return null;
    }
    const session = sessions.get(normalizedConversationId);
    if (!session || !session.active || session.status !== 'streaming' || !session.countsAsStreaming) {
        return null;
    }
    return session;
}

export { resolveActiveStreamingSession };
