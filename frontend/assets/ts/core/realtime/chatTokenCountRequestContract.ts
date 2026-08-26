/* SoAI - Frontend chat token-count WebSocket request contract [frontend/assets/ts/core/realtime/chatTokenCountRequestContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonArray, JsonObject } from '@core/types/jsonValues.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';

interface ChatTokenCountRequest {
    conversationId: string;
    requestId: string;
    openAiRequest: JsonObject;
    draftUserText: string | null;
    draftAttachmentContent: JsonArray;
}

const serializeChatTokenCountRequest = (request: ChatTokenCountRequest): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.CHAT_TOKEN_COUNT,
    'conv_id': request.conversationId,
    'request_id': request.requestId,
    'openai_request': request.openAiRequest,
    ...(request.draftUserText ? { 'draft_user_text': request.draftUserText } : {}),
    ...(request.draftAttachmentContent.length > 0 ? { 'draft_attachment_content': request.draftAttachmentContent } : {})
});

export { serializeChatTokenCountRequest };
export type { ChatTokenCountRequest };
