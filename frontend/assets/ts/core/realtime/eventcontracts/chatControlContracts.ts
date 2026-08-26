/* SoAI - Frontend chat control WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/chatControlContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { decodeTokenUsageSnapshot, type TokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';
import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readNullableFiniteIntegerValue, readRequiredFiniteNumberValue, readRequiredNonNegativeIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface ChatEventBase {
    eventId: string;
    timestamp: number;
    userId: number;
    convId: string;
}
interface ConversationInputsChangedEvent extends ChatEventBase {
    activeCount: number;
    lastModifiedAtMs: number;
}
interface ConversationInputTerminalEvent extends ChatEventBase {
    inputId: string;
    sourceMessageId: number | null;
    terminalState: 'cancelled' | 'completed' | 'effect_unknown' | 'failed';
    terminalCode: string;
}
interface ConversationBoundEvent {
    convId: string;
}
interface ChatTokenCountResultEvent extends ConversationBoundEvent {
    type: 'chat_token_count_result';
    requestId: string;
    usagePreview: TokenUsageSnapshot;
}
interface PromptBudgetDetails {
    type: 'prompt_budget_capped' | 'prompt_budget_exceeded';
    promptTokens: number | null;
    budgetTokens: number;
}
interface ChatTokenCountErrorEvent extends ConversationBoundEvent {
    type: 'chat_token_count_error';
    requestId: string;
    code: string;
    message: string;
    phase: string | null;
    traceId: string | null;
    userMessage: string | null;
    details: OpaqueJsonObject | null;
    promptBudget: PromptBudgetDetails | null;
    usagePreview: TokenUsageSnapshot | null;
}
interface ConversationDraftChangedEvent extends ChatEventBase {
    clientId: string;
    updatedAtMs: number;
    deleted: boolean;
    revision: number;
}

const decodeChatEventBase = (payload: JsonValue): ChatEventBase => {
    const record = requireRecord(payload, 'Chat event');
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], 'Chat event.timestamp');
    if (timestamp <= 0) throw new TypeError('Chat event.timestamp must be positive');
    return { eventId: readRequiredTrimmedStringValue(record['event_id'], 'Chat event.event_id'), timestamp, userId: readRequiredPositiveIntegerValue(record['user_id'], 'Chat event.user_id'), convId: readRequiredTrimmedStringValue(record['conv_id'], 'Chat event.conv_id') };
};

const decodeConversationInputsChanged = (payload: JsonValue): ConversationInputsChangedEvent => {
    const record = requireRecord(payload, 'Conversation inputs changed event');
    return { ...decodeChatEventBase(payload), activeCount: readRequiredNonNegativeIntegerValue(record['active_count'], 'Conversation inputs changed event.active_count'), lastModifiedAtMs: readRequiredPositiveIntegerValue(record['last_modified_at_ms'], 'Conversation inputs changed event.last_modified_at_ms') };
};

const decodeConversationInputTerminal = (payload: JsonValue): ConversationInputTerminalEvent => {
    const record = requireRecord(payload, 'Conversation input terminal event');
    const sourceMessageId = readNullableFiniteIntegerValue(record['source_message_id'], 'Conversation input terminal event.source_message_id');
    if (sourceMessageId !== null && sourceMessageId <= 0) throw new TypeError('Conversation input terminal event.source_message_id must be positive or null');
    return { ...decodeChatEventBase(payload), inputId: readRequiredTrimmedStringValue(record['input_id'], 'Conversation input terminal event.input_id'), sourceMessageId, terminalState: readRequiredEnumValue(record['terminal_state'], 'Conversation input terminal event.terminal_state', ['cancelled', 'completed', 'effect_unknown', 'failed']), terminalCode: readRequiredTrimmedStringValue(record['terminal_code'], 'Conversation input terminal event.terminal_code') };
};

const decodeConversationBound = (payload: JsonValue): ConversationBoundEvent => ({ convId: readRequiredTrimmedStringValue(requireRecord(payload, 'Conversation-bound event')['conv_id'], 'Conversation-bound event.conv_id') });

const requireType = <Type extends string>(record: OpaqueJsonObject, expected: Type): Type => {
    const type = readRequiredStringValue(record['type'], 'Chat command event.type');
    if (type !== expected) throw new TypeError(`Chat command event.type must be ${expected}`);
    return expected;
};

const decodeTokenCountResult = (payload: JsonValue): ChatTokenCountResultEvent => {
    const record = requireRecord(payload, 'Chat token count result');
    return { type: requireType(record, WEBSOCKET_EVENT_TYPES.CHAT_TOKEN_COUNT_RESULT), convId: readRequiredTrimmedStringValue(record['conv_id'], 'Chat token count result.conv_id'), requestId: readRequiredTrimmedStringValue(record['request_id'], 'Chat token count result.request_id'), usagePreview: decodeTokenUsageSnapshot(record['usage_preview'] ?? null) };
};

const decodeTokenCountError = (payload: JsonValue): ChatTokenCountErrorEvent => {
    const record = requireRecord(payload, 'Chat token count error');
    const usageValue = record['usage_preview'];
    const detailsValue = record['details'];
    const details = detailsValue === null || detailsValue === undefined ? null : requireRecord(detailsValue, 'Chat token count error.details');
    let promptBudget: PromptBudgetDetails | null = null;
    if (details?.['type'] === 'prompt_budget_exceeded' || details?.['type'] === 'prompt_budget_capped') {
        const promptTokens = readNullableFiniteIntegerValue(details['prompt_tokens'], 'Chat token count error.details.prompt_tokens');
        const budgetTokens = readRequiredNonNegativeIntegerValue(details['budget_tokens'], 'Chat token count error.details.budget_tokens');
        if (promptTokens !== null && promptTokens < 0) throw new TypeError('Chat token count error.details.prompt_tokens must be non-negative or null');
        promptBudget = { type: details['type'], promptTokens, budgetTokens };
    }
    return { type: requireType(record, WEBSOCKET_EVENT_TYPES.CHAT_TOKEN_COUNT_ERROR), convId: readRequiredTrimmedStringValue(record['conv_id'], 'Chat token count error.conv_id'), requestId: readRequiredTrimmedStringValue(record['request_id'], 'Chat token count error.request_id'), code: readRequiredTrimmedStringValue(record['code'], 'Chat token count error.code'), message: readRequiredStringValue(record['message'], 'Chat token count error.message'), phase: readNullableTrimmedStringValue(record['phase'], 'Chat token count error.phase'), traceId: readNullableTrimmedStringValue(record['trace_id'], 'Chat token count error.trace_id'), userMessage: readNullableTrimmedStringValue(record['user_message'], 'Chat token count error.user_message'), details, promptBudget, usagePreview: usageValue === null || usageValue === undefined ? null : decodeTokenUsageSnapshot(usageValue) };
};

const decodeConversationDraftChanged = (payload: JsonValue): ConversationDraftChangedEvent => {
    const record = requireRecord(payload, 'Conversation draft changed event');
    return {
        ...decodeChatEventBase(payload),
        clientId: readRequiredStringValue(record['client_id'], 'Conversation draft changed event.client_id'),
        updatedAtMs: readRequiredPositiveIntegerValue(record['updated_at_ms'], 'Conversation draft changed event.updated_at_ms'),
        deleted: readRequiredBooleanValue(record['deleted'], 'Conversation draft changed event.deleted'),
        revision: readRequiredPositiveIntegerValue(record['revision'], 'Conversation draft changed event.revision')
    };
};

const CHAT_CONTROL_EVENT_CONTRACTS = Object.freeze({
    inputsChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CONVERSATION_INPUTS_CHANGED, decodeConversationInputsChanged),
    inputTerminal: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CONVERSATION_INPUT_TERMINAL, decodeConversationInputTerminal),
    knowledgePromptChangedIdentity: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.KNOWLEDGE_PROMPT_STATE_CHANGED, decodeConversationBound),
    tokenCountResult: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CHAT_TOKEN_COUNT_RESULT, decodeTokenCountResult),
    tokenCountError: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CHAT_TOKEN_COUNT_ERROR, decodeTokenCountError),
    draftChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CONVERSATION_DRAFT_CHANGED, decodeConversationDraftChanged)
});

export { CHAT_CONTROL_EVENT_CONTRACTS };
export type { ChatTokenCountErrorEvent, ChatTokenCountResultEvent, ConversationBoundEvent, ConversationDraftChangedEvent, ConversationInputTerminalEvent, ConversationInputsChangedEvent, PromptBudgetDetails };
