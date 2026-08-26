/* SoAI - Frontend WebUI conversation message response contracts [frontend/assets/ts/core/api/contracts/webuiMessageContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeWebuiMessageContentPart, type WebuiMessageContent } from '@core/api/contracts/webuiMessageContentPartContract.ts';
import { CHAT_MESSAGE_ROLES, type MessageRole } from '@core/chat/messageRoles.ts';
import { CONVERSATION_MESSAGE_TYPES, type ConversationMessageType } from '@core/chat/conversationMessageType.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredEnumValue, readRequiredEpochMsValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';
import { readRequiredFiniteNumberValue, readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonArray, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { decodeAssistantTimeline, decodeAssistantTimelineProjection } from '@core/realtime/eventcontracts/assistantTimelineContracts.ts';
import { requireAssistantTimelineTool } from '@core/realtime/eventcontracts/assistantToolContracts.ts';
import type { AssistantEventTimelineItem, AssistantTimelineTool, AssistantTimelineType } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';

interface WebuiMessageToolCall {
    id?: string | undefined;
    index?: number | undefined;
    type?: string | undefined;
    function?: JsonObject | undefined;
    output?: string | undefined;
    toolArguments?: JsonValue | undefined;
    functionArguments?: JsonValue | undefined;
    input?: JsonValue | undefined;
    parameters?: JsonValue | undefined;
}

interface WebuiConversationMessageResponse {
    id?: number | undefined;
    conversationInputId?: string | undefined;
    messagingSenderDisplayName?: string | undefined;
    messagingSenderId?: string | undefined;
    role: MessageRole;
    messageType: ConversationMessageType;
    timestamp: number;
    assistantTurnAtMs?: number | null | undefined;
    modelVariantIndex?: number | null | undefined;
    content?: WebuiMessageContent | undefined;
    name?: string | undefined;
    toolCallId?: string | undefined;
    toolCalls?: WebuiMessageToolCall[] | undefined;
    requestId?: string | undefined;
    modelId?: string | undefined;
    promptTokens?: number | undefined;
    completionTokens?: number | undefined;
    totalTokens?: number | undefined;
    usageSource?: string | undefined;
    generationLatencyMs?: number | undefined;
    generationSpeedTokensPerSec?: number | undefined;
    finishReason?: string | undefined;
    thinkingTailDurationMs?: number | undefined;
    assistantEventTimeline?: AssistantEventTimelineItem[] | undefined;
    assistantTimelineType?: AssistantTimelineType | undefined;
    toolCallProjections?: AssistantTimelineTool[] | undefined;
    soaiMessageType?: string | undefined;
    soaiCompaction?: JsonObject | undefined;
    soaiCompactionStats?: JsonObject | undefined;
}

const assertKnownMessageFields = (record: JsonObject, label: string): void => {
    for (const key of Object.keys(record)) {
        switch (key) {
            case 'id':
            case 'conversation_input_id':
            case 'messaging_sender_display_name':
            case 'messaging_sender_id':
            case 'role':
            case 'message_type':
            case 'timestamp':
            case 'assistant_turn_at_ms':
            case 'model_variant_index':
            case 'content':
            case 'name':
            case 'tool_call_id':
            case 'tool_calls':
            case 'request_id':
            case 'model_id':
            case 'prompt_tokens':
            case 'completion_tokens':
            case 'total_tokens':
            case 'usage_source':
            case 'generation_latency_ms':
            case 'generation_speed_tokens_per_sec':
            case 'finish_reason':
            case 'thinking_tail_duration_ms':
            case 'assistant_event_timeline':
            case 'assistant_event_timeline_projection':
            case 'tool_call_projections':
            case 'soai_message_type':
            case 'soai_compaction':
            case 'soai_compaction_stats':
                break;
            default:
                throw new TypeError(`${label} contains unsupported field '${key}'`);
        }
    }
};

const decodeToolCall = (value: JsonValue, label: string): WebuiMessageToolCall => {
    const record = requireRecord(value, label);
    return { id: typeof record['id'] === 'string' ? record['id'] : undefined, index: typeof record['index'] === 'number' ? record['index'] : undefined, type: typeof record['type'] === 'string' ? record['type'] : undefined, function: record['function'] === undefined ? undefined : requireRecord(record['function'], `${label}.function`), output: typeof record['output'] === 'string' ? record['output'] : undefined, toolArguments: record['args'], functionArguments: record['arguments'], input: record['input'], parameters: record['parameters'] };
};

const optionalNonNegativeInteger = (value: JsonValue | undefined, label: string): number | undefined => (value === undefined ? undefined : readRequiredNonNegativeIntegerValue(value, label));
const optionalFiniteNumber = (value: JsonValue | undefined, label: string): number | undefined => (value === undefined ? undefined : readRequiredFiniteNumberValue(value, label));
const optionalEpochMs = (value: JsonValue | undefined, label: string): number | null | undefined => (value === undefined ? undefined : value === null ? null : readRequiredEpochMsValue(value, label));
const optionalString = (value: JsonValue | undefined, label: string): string | undefined => (value === undefined ? undefined : readRequiredStringValue(value, label));

const decodeMessage = (value: JsonValue, label: string): WebuiConversationMessageResponse => {
    const record = requireRecord(value, label);
    assertKnownMessageFields(record, label);
    const content = record['content'];
    const toolCalls = record['tool_calls'];
    const toolCallProjections = record['tool_call_projections'];
    const assistantEventTimeline = record['assistant_event_timeline'];
    const assistantEventTimelineProjection = record['assistant_event_timeline_projection'];
    const role = readRequiredEnumValue(record['role'], `${label}.role`, CHAT_MESSAGE_ROLES);
    if (role === 'assistant' && (assistantEventTimeline === undefined) === (assistantEventTimelineProjection === undefined)) {
        throw new TypeError(`${label} must contain exactly one assistant timeline representation.`);
    }
    if (role !== 'assistant' && (assistantEventTimeline !== undefined || assistantEventTimelineProjection !== undefined)) {
        throw new TypeError(`${label} timeline fields are only supported for assistant messages.`);
    }
    return {
        id: record['id'] === undefined ? undefined : readRequiredNonNegativeIntegerValue(record['id'], `${label}.id`),
        conversationInputId: optionalString(record['conversation_input_id'], `${label}.conversation_input_id`),
        messagingSenderDisplayName: optionalString(record['messaging_sender_display_name'], `${label}.messaging_sender_display_name`),
        messagingSenderId: optionalString(record['messaging_sender_id'], `${label}.messaging_sender_id`),
        role,
        messageType: readRequiredEnumValue(record['message_type'], `${label}.message_type`, CONVERSATION_MESSAGE_TYPES),
        timestamp: readRequiredEpochMsValue(record['timestamp'], `${label}.timestamp`),
        assistantTurnAtMs: optionalEpochMs(record['assistant_turn_at_ms'], `${label}.assistant_turn_at_ms`),
        modelVariantIndex: record['model_variant_index'] === null ? null : optionalNonNegativeInteger(record['model_variant_index'], `${label}.model_variant_index`),
        content:
            content === undefined || content === null || typeof content === 'string'
                ? content
                : isJsonArray(content)
                  ? content.map((entry, index) => decodeWebuiMessageContentPart(entry, `${label}.content[${String(index)}]`))
                  : (() => {
                        throw new TypeError(`${label}.content must be a string, null, or content-part array.`);
                    })(),
        name: optionalString(record['name'], `${label}.name`),
        toolCallId: optionalString(record['tool_call_id'], `${label}.tool_call_id`),
        toolCalls:
            toolCalls === undefined
                ? undefined
                : isJsonArray(toolCalls)
                  ? toolCalls.map((entry, index) => decodeToolCall(entry, `${label}.tool_calls[${String(index)}]`))
                  : (() => {
                        throw new TypeError(`${label}.tool_calls must be an array.`);
                    })(),
        requestId: optionalString(record['request_id'], `${label}.request_id`),
        modelId: optionalString(record['model_id'], `${label}.model_id`),
        promptTokens: optionalNonNegativeInteger(record['prompt_tokens'], `${label}.prompt_tokens`),
        completionTokens: optionalNonNegativeInteger(record['completion_tokens'], `${label}.completion_tokens`),
        totalTokens: optionalNonNegativeInteger(record['total_tokens'], `${label}.total_tokens`),
        usageSource: optionalString(record['usage_source'], `${label}.usage_source`),
        generationLatencyMs: optionalNonNegativeInteger(record['generation_latency_ms'], `${label}.generation_latency_ms`),
        generationSpeedTokensPerSec: optionalFiniteNumber(record['generation_speed_tokens_per_sec'], `${label}.generation_speed_tokens_per_sec`),
        finishReason: optionalString(record['finish_reason'], `${label}.finish_reason`),
        thinkingTailDurationMs: optionalNonNegativeInteger(record['thinking_tail_duration_ms'], `${label}.thinking_tail_duration_ms`),
        assistantEventTimeline: assistantEventTimeline !== undefined ? decodeAssistantTimeline(assistantEventTimeline) : assistantEventTimelineProjection !== undefined ? decodeAssistantTimelineProjection(assistantEventTimelineProjection) : undefined,
        assistantTimelineType: assistantEventTimeline !== undefined ? 'canonical' : assistantEventTimelineProjection !== undefined ? 'projection' : undefined,
        toolCallProjections:
            toolCallProjections === undefined
                ? undefined
                : isJsonArray(toolCallProjections)
                  ? toolCallProjections.map((entry, index) => requireAssistantTimelineTool(entry, `${label}.tool_call_projections[${String(index)}]`))
                  : (() => {
                        throw new TypeError(`${label}.tool_call_projections must be an array.`);
                    })(),
        soaiMessageType: optionalString(record['soai_message_type'], `${label}.soai_message_type`),
        soaiCompaction: record['soai_compaction'] === undefined ? undefined : requireRecord(record['soai_compaction'], `${label}.soai_compaction`),
        soaiCompactionStats: record['soai_compaction_stats'] === undefined ? undefined : requireRecord(record['soai_compaction_stats'], `${label}.soai_compaction_stats`)
    };
};

const decodeMessageArray = (value: JsonValue | undefined, label: string): WebuiConversationMessageResponse[] => {
    if (!isJsonArray(value)) throw new TypeError(`${label} must be an array.`);
    return value.map((entry, index) => decodeMessage(entry, `${label}[${String(index)}]`));
};

const decodeMessageResponse = (value: ApiResponsePayload, label: string): WebuiConversationMessageResponse => decodeMessage(requireRecord(value, label), label);

export { decodeMessage, decodeMessageArray, decodeMessageResponse };
export type { WebuiConversationMessageResponse, WebuiMessageContent, WebuiMessageToolCall };
