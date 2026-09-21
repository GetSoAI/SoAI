/* SoAI - Durable conversation message regeneration API contracts [frontend/assets/ts/core/api/contracts/webuiMessageRegenerationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredNonEmptyStringValue } from '@core/types/payloadValueReaders.ts';
import { readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableJsonObjectValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

type ConversationRegenerationState = 'pending' | 'materializing' | 'running' | 'input_required' | 'completed' | 'failed' | 'cancelled' | 'effect_unknown';

interface ConversationRegenerationRequest {
    clientId: string;
    clientRequestId: string;
    expectedLastModifiedAtMs: number;
    target: { createdAtMs: number; messageId: number } | null;
    retryInputId: string | null;
    contentPreviewFeedback: JsonObject | null;
    previewContractFeedback: JsonObject | null;
}

interface ConversationRegenerationReceipt {
    inputId: string;
    requestId: string;
    assistantAtMs: number;
    assistantTurnAtMs: number;
    acceptedAtMs: number;
    lastModifiedAtMs: number;
    state: ConversationRegenerationState;
    isDispatchableHead: boolean;
    hasAssistantReplacement: boolean;
    terminalCode: string | null;
    terminalArguments: JsonObject | null;
    contentPreviewFeedback: JsonObject | null;
    previewContractFeedback: JsonObject | null;
}

const serializeConversationRegenerationRequest = (request: ConversationRegenerationRequest): JsonObject => {
    const payload: JsonObject = {
        'client_id': request.clientId,
        'client_request_id': request.clientRequestId,
        'expected_last_modified_at_ms': request.expectedLastModifiedAtMs
    };
    if (request.target !== null) {
        payload['target'] = {
            'created_at_ms': request.target.createdAtMs,
            'message_id': request.target.messageId
        };
    } else if (request.retryInputId !== null) {
        payload['retry_input_id'] = request.retryInputId;
    }
    if (request.contentPreviewFeedback !== null) payload['content_preview_feedback'] = request.contentPreviewFeedback;
    if (request.previewContractFeedback !== null) payload['preview_contract_feedback'] = request.previewContractFeedback;
    return payload;
};

const decodeConversationRegenerationReceipt = (value: ApiResponsePayload): ConversationRegenerationReceipt => {
    const record = requireRecord(value, 'Conversation regeneration response');
    return {
        inputId: readRequiredNonEmptyStringValue(record['input_id'], 'Conversation regeneration response.input_id'),
        requestId: readRequiredNonEmptyStringValue(record['request_id'], 'Conversation regeneration response.request_id'),
        assistantAtMs: readRequiredPositiveIntegerValue(record['assistant_at_ms'], 'Conversation regeneration response.assistant_at_ms'),
        assistantTurnAtMs: readRequiredPositiveIntegerValue(record['assistant_turn_at_ms'], 'Conversation regeneration response.assistant_turn_at_ms'),
        acceptedAtMs: readRequiredPositiveIntegerValue(record['accepted_at_ms'], 'Conversation regeneration response.accepted_at_ms'),
        lastModifiedAtMs: readRequiredPositiveIntegerValue(record['last_modified_at_ms'], 'Conversation regeneration response.last_modified_at_ms'),
        state: readRequiredEnumValue(record['state'], 'Conversation regeneration response.state', ['pending', 'materializing', 'running', 'input_required', 'completed', 'failed', 'cancelled', 'effect_unknown']),
        isDispatchableHead: readRequiredBooleanValue(record['is_dispatchable_head'], 'Conversation regeneration response.is_dispatchable_head'),
        hasAssistantReplacement: readRequiredBooleanValue(record['has_assistant_replacement'], 'Conversation regeneration response.has_assistant_replacement'),
        terminalCode: readNullableTrimmedStringValue(record['terminal_code'], 'Conversation regeneration response.terminal_code'),
        terminalArguments: readNullableJsonObjectValue(record['terminal_args'], 'Conversation regeneration response.terminal_args'),
        contentPreviewFeedback: readNullableJsonObjectValue(record['content_preview_feedback'], 'Conversation regeneration response.content_preview_feedback'),
        previewContractFeedback: readNullableJsonObjectValue(record['preview_contract_feedback'], 'Conversation regeneration response.preview_contract_feedback')
    };
};

export { decodeConversationRegenerationReceipt, serializeConversationRegenerationRequest };
export type { ConversationRegenerationReceipt, ConversationRegenerationRequest, ConversationRegenerationState };
