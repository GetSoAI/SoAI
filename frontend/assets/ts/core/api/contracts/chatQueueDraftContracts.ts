/* SoAI - Frontend chat queue and draft boundary contracts [frontend/assets/ts/core/api/contracts/chatQueueDraftContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { MAX_CHAT_COMPOSER_TEXT_LENGTH } from '@core/chat/protocols.ts';
import { decodeWebuiMessageContentPart, type WebuiMessageContentPart } from '@core/api/contracts/webuiMessageContentPartContract.ts';
import { readRequiredNonNegativeIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredJsonObjectArrayValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredEnumValue, readRequiredNonEmptyStringValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type ConversationInputType = 'prompt' | 'steer' | 'control';
type ConversationInputState = 'pending' | 'materializing' | 'running' | 'input_required';

interface ConversationInput {
    inputId: string;
    inputType: ConversationInputType;
    text: string;
    attachmentContent: WebuiMessageContentPart[];
    acceptedAtMs: number;
    state: ConversationInputState;
}

interface ConversationInputAdmission extends ConversationInput {
    isDispatchableHead: boolean;
}

interface ConversationInputListResponse {
    items: ConversationInput[];
}

interface ConversationInputEnqueueRequest {
    inputType: 'prompt' | 'steer';
    text: string | null;
    promptHistoryText: string | null;
    attachmentContent: JsonObject[];
    clientId: string;
    clientRequestId: string;
}

interface ConversationDraft {
    convId: string;
    userId: number;
    text: string;
    sourceText: string;
    attachmentContent: JsonValue[];
    attachments: JsonObject[];
    droppedAttachmentCount: number;
    createdAtMs: number;
    updatedAtMs: number;
    clientId: string;
}

interface ConversationDraftResponse {
    draft: ConversationDraft | null;
    revision: number;
}

interface ConversationDraftSaveRequest {
    text: string | null;
    sourceText: string;
    attachmentContent: JsonValue[];
    clientId: string;
    clientSequence: number;
    baseRevision: number;
}

const decodeAttachmentContent = (value: JsonValue | undefined, label: string): WebuiMessageContentPart[] => {
    const entries = readRequiredJsonObjectArrayValue(value, label);
    return entries.map((entry, index) => decodeWebuiMessageContentPart(entry, `${label}[${String(index)}]`));
};

const decodeConversationInput = (value: JsonValue, index: number): ConversationInput => {
    const label = `Conversation input response[${String(index)}]`;
    const record = requireRecord(value, label);
    const text = readRequiredStringValue(record['text'], `${label}.text`);
    const attachmentContent = decodeAttachmentContent(record['attachment_content'], `${label}.attachment_content`);
    if (!text.trim() && attachmentContent.length === 0) throw new TypeError(`${label} must include text or attachment_content.`);
    return {
        inputId: readRequiredNonEmptyStringValue(record['input_id'], `${label}.input_id`).trim(),
        inputType: readRequiredEnumValue(record['input_type'], `${label}.input_type`, ['prompt', 'steer', 'control']),
        text: text.trim(),
        attachmentContent: attachmentContent,
        acceptedAtMs: readRequiredPositiveIntegerValue(record['accepted_at_ms'], `${label}.accepted_at_ms`),
        state: readRequiredEnumValue(record['state'], `${label}.state`, ['pending', 'materializing', 'running', 'input_required'])
    };
};

const decodeConversationInputList = (value: ApiResponsePayload): ConversationInputListResponse => {
    const record = requireRecord(value, 'Conversation inputs list response');
    return { items: readRequiredJsonObjectArrayValue(record['items'], 'Conversation inputs list response.items').map(decodeConversationInput) };
};

const decodeConversationInputCreated = (value: ApiResponsePayload): ConversationInputAdmission => {
    const record = requireRecord(value, 'Conversation input create response');
    return {
        ...decodeConversationInput(record, 0),
        isDispatchableHead: readRequiredBooleanValue(record['is_dispatchable_head'], 'Conversation input create response.is_dispatchable_head')
    };
};

const decodeConversationDraft = (value: JsonValue): ConversationDraft => {
    const label = 'Conversation draft response.draft';
    const record = requireRecord(value, label);
    const attachmentContent = record['attachment_content'];
    if (!Array.isArray(attachmentContent)) throw new TypeError(`${label}.attachment_content must be an array.`);
    const text = readRequiredStringValue(record['text'], `${label}.text`);
    const sourceText = readRequiredStringValue(record['source_text'], `${label}.source_text`);
    if (text.length > MAX_CHAT_COMPOSER_TEXT_LENGTH || sourceText.length > MAX_CHAT_COMPOSER_TEXT_LENGTH) throw new TypeError(`${label} text exceeds the maximum length.`);
    return {
        convId: readRequiredNonEmptyStringValue(record['conv_id'], `${label}.conv_id`),
        userId: readRequiredPositiveIntegerValue(record['user_id'], `${label}.user_id`),
        text,
        sourceText,
        attachmentContent: attachmentContent,
        attachments: readRequiredJsonObjectArrayValue(record['attachments'], `${label}.attachments`),
        droppedAttachmentCount: readRequiredNonNegativeIntegerValue(record['dropped_attachment_count'], `${label}.dropped_attachment_count`),
        createdAtMs: readRequiredPositiveIntegerValue(record['created_at_ms'], `${label}.created_at_ms`),
        updatedAtMs: readRequiredPositiveIntegerValue(record['updated_at_ms'], `${label}.updated_at_ms`),
        clientId: readRequiredNonEmptyStringValue(record['client_id'], `${label}.client_id`)
    };
};

const decodeConversationDraftResponse = (value: ApiResponsePayload): ConversationDraftResponse => {
    const record = requireRecord(value, 'Conversation draft response');
    const draft = record['draft'];
    return {
        draft: draft === null || draft === undefined ? null : decodeConversationDraft(draft),
        revision: readRequiredNonNegativeIntegerValue(record['revision'], 'Conversation draft response.revision')
    };
};

const serializeConversationInputEnqueueRequest = (request: ConversationInputEnqueueRequest): JsonObject => ({
    'input_type': request.inputType,
    text: request.text,
    'prompt_history_text': request.promptHistoryText,
    'attachment_content': request.attachmentContent,
    'client_id': request.clientId,
    'client_request_id': request.clientRequestId
});

const serializeConversationDraftSaveRequest = (request: ConversationDraftSaveRequest): JsonObject => ({
    text: request.text,
    'source_text': request.sourceText,
    'attachment_content': request.attachmentContent,
    'client_id': request.clientId,
    'client_sequence': request.clientSequence,
    'base_revision': request.baseRevision
});

export { decodeConversationDraftResponse, decodeConversationInputCreated, decodeConversationInputList, serializeConversationDraftSaveRequest, serializeConversationInputEnqueueRequest };
export type { ConversationDraft, ConversationDraftResponse, ConversationDraftSaveRequest, ConversationInput, ConversationInputAdmission, ConversationInputEnqueueRequest, ConversationInputListResponse, ConversationInputState, ConversationInputType };
