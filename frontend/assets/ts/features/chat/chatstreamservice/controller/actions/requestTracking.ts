/* SoAI - Chat feature request tracking [frontend/assets/ts/features/chat/chatstreamservice/controller/actions/requestTracking.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { generateSecureId } from '@core/primitives/idGenerator.ts';
import type { ChatStreamingControllerContext } from '@features/chat/chatstreamservice/controller/types.ts';

const beginRequestToken = (context: ChatStreamingControllerContext, conversationId: string): number => {
    const token = (context.requestTokenByConversationId.get(conversationId) ?? 0) + 1;
    context.requestTokenByConversationId.set(conversationId, token);
    return token;
};

const invalidateRequestToken = (context: ChatStreamingControllerContext, conversationId: string): void => {
    const token = (context.requestTokenByConversationId.get(conversationId) ?? 0) + 1;
    context.requestTokenByConversationId.set(conversationId, token);
};

const buildRequestId = (conversationId: string, requestToken: number): string => {
    return `${conversationId}:${String(requestToken)}:${generateSecureId({ format: 'hex' })}`;
};

const isActiveRequest = (context: ChatStreamingControllerContext, conversationId: string, requestToken: number): boolean => {
    if (context.disposed) {
        return false;
    }
    return context.requestTokenByConversationId.get(conversationId) === requestToken;
};

export { beginRequestToken, buildRequestId, invalidateRequestToken, isActiveRequest };
