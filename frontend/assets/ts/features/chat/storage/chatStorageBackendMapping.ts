/* SoAI - Backend chat message payload normalization [frontend/assets/ts/features/chat/storage/chatStorageBackendMapping.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiConversationMessageResponse, WebuiMessageContent, WebuiMessageToolCall } from '@core/api/contracts/webuiMessageContracts.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { isBoolean, isNumber, isString } from '@core/typeGuards.ts';
import type { ChatContent, ChatMessage, SoaiCompactionMarker, ToolActivityItem, ToolCall } from '@features/chat/ChatTypes.ts';
import { mapDecodedAssistantTimelineTool } from '@features/chat/assistanteventtimeline/toolPayloadMapper.ts';
import type { AssistantTimelineTool } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import type { ChatStorageMessageRecord } from '@features/chat/storage/storageModels.ts';
import { sortToolCallProjectionsBySequence } from '@features/chat/toolactivity/toolProjectionMutation.ts';
import { requireAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';

const mapContent = (content: WebuiMessageContent): ChatContent => (Array.isArray(content) ? [...content] : content);

const mapToolCall = (toolCall: WebuiMessageToolCall): ToolCall => {
    const mapped: ToolCall = {};
    if (toolCall.id !== undefined) mapped.id = toolCall.id;
    if (toolCall.index !== undefined) mapped.index = toolCall.index;
    if (toolCall.type !== undefined) mapped.type = toolCall.type;
    if (toolCall.output !== undefined) mapped.output = toolCall.output;
    if (toolCall.toolArguments !== undefined) mapped.toolArguments = toolCall.toolArguments;
    if (toolCall.functionArguments !== undefined) mapped.functionArguments = toolCall.functionArguments;
    if (toolCall.input !== undefined) mapped.input = toolCall.input;
    if (toolCall.parameters !== undefined) mapped.parameters = toolCall.parameters;
    if (toolCall.function !== undefined) {
        const functionName = toolCall.function['name'];
        const functionArguments = toolCall.function['arguments'];
        if (functionName !== undefined && !isString(functionName)) throw new Error('Backend message tool call function name must be a string');
        if (functionArguments !== undefined && !isString(functionArguments)) throw new Error('Backend message tool call function arguments must be a string');
        mapped.function = {};
        if (functionName !== undefined) mapped.function.name = functionName;
        if (functionArguments !== undefined) mapped.function.serializedArguments = functionArguments;
    }
    return mapped;
};

const mapToolCallProjections = (value: readonly AssistantTimelineTool[] | undefined): ToolActivityItem[] | undefined => {
    if (value === undefined) return undefined;
    const projections: ToolActivityItem[] = [];
    for (let index = 0; index < value.length; index += 1) {
        const projection = value[index];
        if (projection === undefined) throw new Error(`Backend message tool_call_projections[${String(index)}] is missing`);
        projections.push(mapDecodedAssistantTimelineTool(projection));
    }
    sortToolCallProjectionsBySequence(projections);
    return projections;
};

const mapCompactionStats = (value: JsonObject | undefined): { count: number; tokensSaved: number } | undefined => {
    if (value === undefined) return undefined;
    const count = value['count'];
    const tokensSaved = value['tokens_saved'];
    if (!isNumber(count) || !Number.isInteger(count) || count <= 0) throw new Error('Backend message soai_compaction_stats count must be a positive integer');
    if (!isNumber(tokensSaved) || !Number.isInteger(tokensSaved) || tokensSaved < 0) throw new Error('Backend message soai_compaction_stats tokens_saved must be a non-negative integer');
    return { count, tokensSaved };
};

const mapCompactionMarker = (value: JsonObject): SoaiCompactionMarker => {
    const marker: SoaiCompactionMarker = {};
    const toolCallId = value['tool_call_id'];
    if (toolCallId !== undefined && toolCallId !== null && !isString(toolCallId)) throw new Error('Backend message soai_compaction.tool_call_id must be a string or null');
    if (toolCallId !== undefined) marker.toolCallId = toolCallId;
    const status = value['status'];
    if (status !== undefined && !isString(status)) throw new Error('Backend message soai_compaction.status must be a string');
    if (status !== undefined) marker.status = status;
    const output = value['output'];
    if (output !== undefined && output !== null && !isString(output)) throw new Error('Backend message soai_compaction.output must be a string or null');
    if (output !== undefined) marker.output = output;
    const trigger = value['trigger'];
    if (trigger !== undefined && trigger !== null && !isString(trigger)) throw new Error('Backend message soai_compaction.trigger must be a string or null');
    if (trigger !== undefined) marker.trigger = trigger;
    const model = value['model'];
    if (model !== undefined && model !== null && !isString(model)) throw new Error('Backend message soai_compaction.model must be a string or null');
    if (model !== undefined) marker.model = model;
    const details = value['details'];
    if (details !== undefined && !isJsonObject(details)) throw new Error('Backend message soai_compaction.details must be an object');
    if (details !== undefined) marker.details = details;
    const promptMessage = value['prompt_message'];
    if (promptMessage !== undefined) {
        if (!isJsonObject(promptMessage) || !isString(promptMessage['role']) || !isString(promptMessage['content'])) throw new Error('Backend message soai_compaction.prompt_message must contain role and content strings');
        const promptName = promptMessage['name'];
        if (promptName !== undefined && !isString(promptName)) throw new Error('Backend message soai_compaction.prompt_message.name must be a string');
        marker.promptMessage = { role: promptMessage['role'], content: promptMessage['content'] };
        if (promptName !== undefined) marker.promptMessage.name = promptName;
    }
    const boundaryRemovedAtMs = value['boundary_removed_at_ms'];
    if (boundaryRemovedAtMs !== undefined && (!isNumber(boundaryRemovedAtMs) || !Number.isInteger(boundaryRemovedAtMs) || boundaryRemovedAtMs <= 0)) throw new Error('Backend message soai_compaction.boundary_removed_at_ms must be a positive integer');
    if (boundaryRemovedAtMs !== undefined) marker.boundaryRemovedAtMs = boundaryRemovedAtMs;
    const boundaryRemovedReason = value['boundary_removed_reason'];
    if (boundaryRemovedReason !== undefined && !isString(boundaryRemovedReason)) throw new Error('Backend message soai_compaction.boundary_removed_reason must be a string');
    if (boundaryRemovedReason !== undefined) marker.boundaryRemovedReason = boundaryRemovedReason;
    const sequenceIndex = value['sequence_index'];
    if (sequenceIndex !== undefined && (!isNumber(sequenceIndex) || !Number.isInteger(sequenceIndex) || sequenceIndex < 0)) throw new Error('Backend message soai_compaction.sequence_index must be a non-negative integer');
    if (sequenceIndex !== undefined) marker.sequenceIndex = sequenceIndex;
    const isActiveBoundary = value['is_active_boundary'];
    if (isActiveBoundary !== undefined && !isBoolean(isActiveBoundary)) throw new Error('Backend message soai_compaction.is_active_boundary must be a boolean');
    if (isActiveBoundary !== undefined) marker.isActiveBoundary = isActiveBoundary;
    return marker;
};

const mapMessageFields = (message: WebuiConversationMessageResponse): ChatMessage => {
    const mapped: ChatMessage = { role: message.role, timestamp: message.timestamp, messageType: message.messageType };
    if (message.id !== undefined) mapped.id = message.id;
    if (message.conversationInputId !== undefined) mapped.soaiConversationInputId = message.conversationInputId;
    if (message.messagingSenderDisplayName !== undefined) mapped.messagingSenderDisplayName = message.messagingSenderDisplayName;
    if (message.messagingSenderId !== undefined) mapped.messagingSenderId = message.messagingSenderId;
    if (message.content !== undefined) mapped.content = mapContent(message.content);
    if (message.assistantTurnAtMs !== undefined) mapped.assistantTurnAtMs = message.assistantTurnAtMs;
    if (message.modelVariantIndex !== undefined) mapped.modelVariantIndex = message.modelVariantIndex;
    if (message.name !== undefined) mapped.name = message.name;
    if (message.toolCallId !== undefined) mapped.toolCallId = message.toolCallId;
    if (message.toolCalls !== undefined) mapped.toolCalls = message.toolCalls.map(mapToolCall);
    if (message.requestId !== undefined) mapped.requestId = message.requestId;
    if (message.modelId !== undefined) mapped.modelId = message.modelId;
    if (message.promptTokens !== undefined) mapped.promptTokens = message.promptTokens;
    if (message.completionTokens !== undefined) mapped.completionTokens = message.completionTokens;
    if (message.totalTokens !== undefined) mapped.totalTokens = message.totalTokens;
    if (message.usageSource !== undefined) mapped.usageSource = message.usageSource;
    if (message.generationLatencyMs !== undefined) mapped.generationLatencyMs = message.generationLatencyMs;
    if (message.generationSpeedTokensPerSec !== undefined) mapped.generationSpeedTokensPerSec = message.generationSpeedTokensPerSec;
    if (message.finishReason !== undefined) mapped.finishReason = message.finishReason;
    if (message.thinkingTailDurationMs !== undefined) mapped.thinkingTailDurationMs = message.thinkingTailDurationMs;
    if (message.assistantEventTimeline !== undefined) mapped.assistantEventTimeline = message.assistantEventTimeline;
    if (message.assistantTimelineType !== undefined) mapped.assistantTimelineType = message.assistantTimelineType;
    const projections = mapToolCallProjections(message.toolCallProjections);
    if (projections !== undefined) mapped.toolCallProjections = projections;
    if (message.soaiMessageType !== undefined) mapped.soaiMessageType = message.soaiMessageType;
    if (message.soaiCompaction !== undefined) mapped.soaiCompaction = mapCompactionMarker(message.soaiCompaction);
    const compactionStats = mapCompactionStats(message.soaiCompactionStats);
    if (compactionStats !== undefined) mapped.soaiCompactionStats = compactionStats;
    return mapped;
};

const validateAssistantMessage = (message: ChatStorageMessageRecord, index: number): void => {
    if (message.assistantTurnAtMs === undefined || message.assistantTurnAtMs === null) throw new Error(`Backend assistant message[${String(index)}] missing assistant_turn_at_ms`);
    if (message.modelVariantIndex === undefined || message.modelVariantIndex === null) throw new Error(`Backend assistant message[${String(index)}] missing model_variant_index`);
    const identity = requireAssistantMessageIdentity({
        assistantTimestamp: message.timestamp,
        assistantTurnTimestamp: message.assistantTurnAtMs,
        modelVariantIndex: message.modelVariantIndex,
        context: `Backend assistant message[${String(index)}]`
    });
    message.assistantTurnAtMs = identity.assistantTurnTimestamp;
    message.modelVariantIndex = identity.modelVariantIndex;
    if (message.assistantEventTimeline === undefined) throw new Error(`Backend assistant message[${String(index)}] missing assistant_event_timeline`);
};

const validateRoleSpecificFields = (message: ChatStorageMessageRecord, index: number): void => {
    if (message.role === 'assistant') {
        validateAssistantMessage(message, index);
        return;
    }
    if (message.assistantTurnAtMs !== undefined && message.assistantTurnAtMs !== null) throw new Error('Backend message assistant_turn_at_ms is only supported for assistant messages');
    if (message.modelVariantIndex !== undefined && message.modelVariantIndex !== null) throw new Error('Backend message model_variant_index is only supported for assistant messages');
    if (message.requestId !== undefined && message.requestId !== null) throw new Error('Backend message request_id is only supported for assistant messages');
    if (message.usageSource !== undefined) throw new Error('Backend message usage_source is only supported for assistant messages');
    if (message.soaiCompactionStats !== undefined) throw new Error('Backend message soai_compaction_stats is only supported for assistant messages');
};

const normalizeMessageTimestamps = (messages: readonly WebuiConversationMessageResponse[]): ChatStorageMessageRecord[] => {
    let previousTimestamp: number | null = null;
    let previousMessageId: number | null = null;
    const normalizedMessages: ChatStorageMessageRecord[] = [];
    for (let index = 0; index < messages.length; index += 1) {
        const source = messages[index];
        if (!source) throw new Error(`Backend message[${String(index)}] is missing`);
        if (!isEpochMsNumber(source.timestamp)) throw new Error(`Backend message[${String(index)}] timestamp must be a positive epoch value`);
        const messageId = typeof source.id === 'number' ? source.id : null;
        if (previousTimestamp !== null && source.timestamp < previousTimestamp) throw new Error(`Backend messages must be chronological at index ${String(index)}`);
        if (previousTimestamp !== null && source.timestamp === previousTimestamp) {
            if (previousMessageId === null || messageId === null) throw new Error(`Backend messages with duplicate timestamps require ids at index ${String(index)}`);
            if (messageId <= previousMessageId) throw new Error(`Backend messages must be ordered by timestamp and id at index ${String(index)}`);
        }
        const normalized = mapMessageFields(source);
        const message: ChatStorageMessageRecord = { ...normalized, role: source.role, timestamp: source.timestamp };
        validateRoleSpecificFields(message, index);
        normalizedMessages.push(message);
        previousTimestamp = source.timestamp;
        previousMessageId = messageId;
    }
    return normalizedMessages;
};

export { normalizeMessageTimestamps };
