/* SoAI - Durable conversation input enqueue request construction [frontend/assets/ts/features/chat/conversationinputs/conversationInputEnqueueRequest.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationInputEnqueueRequest } from '@core/api/contracts/chatQueueDraftContracts.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { containsSoaiPathToken } from '@core/soailinks/codec.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ChatContentSegment } from '@features/chat/ChatTypes.ts';
import { serializeStorageContentPart } from '@features/chat/storage/messageNormalization.ts';

interface ConversationInputEnqueuePayload {
    intent: 'queued' | 'steer';
    text: string | null;
    sourceText: string | null;
    attachmentContent: readonly ChatContentSegment[];
}

const buildConversationInputEnqueueRequest = (payload: ConversationInputEnqueuePayload, clientId: string): ConversationInputEnqueueRequest => {
    const text = toTrimmedString(payload.text) || null;
    const promptHistoryText = toTrimmedString(payload.sourceText) || null;
    const attachmentContent: JsonObject[] = [];
    for (const entry of payload.attachmentContent) {
        const serialized = serializeStorageContentPart(entry);
        if (!isJsonObject(serialized)) {
            throw new Error('Conversation input attachment_content entries must serialize to objects.');
        }
        attachmentContent.push(serialized);
    }
    if (text === null && attachmentContent.length === 0) {
        throw new Error('Conversation input enqueue requires text or attachment_content.');
    }
    if (text !== null && promptHistoryText === null) throw new Error('Conversation input source text must accompany textual input.');
    if (text === null && promptHistoryText !== null && !containsSoaiPathToken(promptHistoryText)) throw new Error('Attachment-only conversation input cannot include source text.');
    const isSteer = payload.intent === 'steer';
    return {
        inputType: isSteer ? 'steer' : 'prompt',
        text,
        promptHistoryText,
        attachmentContent,
        clientId,
        clientRequestId: generateSecureId({ prefix: 'cinput_req', separator: '_' }),
        fallbackToPrompt: isSteer
    };
};

export { buildConversationInputEnqueueRequest };
export type { ConversationInputEnqueuePayload };
