/* SoAI - API chat message normalization [frontend/assets/ts/features/chat/apimessagemapping/normalizeChatMessageForApi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isMessageRole } from '@core/chat/messageRoles.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import { isNonNegativeInteger, isNumber, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ToolCall } from '@features/chat/ChatTypes.ts';
import { parseAssistantTimeline } from '@core/realtime/eventcontracts/assistantTimelineContracts.ts';
import type { ApiChatMessage } from '@features/chat/apimessagemapping/types.ts';
import { normalizeMessageContentForApi } from '@features/chat/apimessagemapping/normalizeChatMessageContentForApi.ts';
import { resolveAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';

const normalizeAssistantToolCall = (value: JsonValue): ToolCall | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const idValue = value['id'];
    const typeValue = value['type'];
    const functionValue = value['function'];
    if (!isString(idValue) || !idValue.trim()) {
        return null;
    }
    if (!isString(typeValue) || !typeValue.trim()) {
        return null;
    }
    if (!isJsonObject(functionValue)) {
        return null;
    }
    const functionName = functionValue['name'];
    if (!isString(functionName) || !functionName.trim()) {
        return null;
    }
    const functionArguments = functionValue['arguments'];
    if (functionArguments !== undefined && functionArguments !== null && !isString(functionArguments)) {
        return null;
    }
    const normalizedFunction: ToolCall['function'] = {
        name: functionName.trim()
    };
    if (isString(functionArguments)) {
        normalizedFunction.serializedArguments = functionArguments;
    }
    return {
        id: idValue.trim(),
        type: typeValue.trim(),
        function: normalizedFunction
    };
};

const normalizeChatMessageForApi = (message: JsonValue): ApiChatMessage | null => {
    if (!isJsonObject(message)) {
        return null;
    }
    const record = message;
    const roleValue = record['role'];
    if (!isString(roleValue) || !roleValue.trim()) {
        return null;
    }
    const role = roleValue.trim().toLowerCase();
    if (!isMessageRole(role)) {
        return null;
    }
    const normalizedContent = normalizeMessageContentForApi(record['content']);
    if (normalizedContent === null) {
        return null;
    }
    if ((role === 'user' || role === 'system' || role === 'developer') && isString(normalizedContent) && !normalizedContent.trim()) {
        return null;
    }
    const timestampValue = record['timestamp'];
    if (!isNumber(timestampValue) || !isEpochMsNumber(timestampValue)) {
        return null;
    }
    const result: ApiChatMessage = { role, content: normalizedContent, timestamp: timestampValue };
    const nameValue = record['name'];
    if (isString(nameValue) && nameValue.trim()) {
        result.name = nameValue.trim();
    }
    const toolCallsValue = isJsonArray(record['tool_calls']) ? record['tool_calls'] : undefined;
    if (role === 'assistant' && toolCallsValue !== undefined && toolCallsValue.length > 0) {
        const toolCalls: ToolCall[] = [];
        for (const entry of toolCallsValue) {
            const normalizedToolCall = normalizeAssistantToolCall(entry);
            if (!normalizedToolCall) {
                return null;
            }
            toolCalls.push(normalizedToolCall);
        }
        if (toolCalls.length > 0) {
            result.toolCalls = toolCalls;
        }
    }
    if (role === 'assistant') {
        const timelineValue = record['assistant_event_timeline'];
        if (timelineValue === undefined || timelineValue === null) {
            result.assistantEventTimeline = [];
        } else {
            const timeline = parseAssistantTimeline(timelineValue);
            if (timeline === null) return null;
            result.assistantEventTimeline = timeline;
        }
    }
    const toolCallIdValue = isString(record['tool_call_id']) ? record['tool_call_id'] : undefined;
    if (role === 'tool') {
        if (isString(toolCallIdValue) && toolCallIdValue.trim()) {
            result.toolCallId = toolCallIdValue.trim();
        } else {
            return null;
        }
    }
    const modelIdValue = record['model_id'];
    if (isString(modelIdValue) && modelIdValue.trim()) {
        result.modelId = modelIdValue.trim();
    }
    const assistantTurnTimestampValue = record['assistant_turn_at_ms'];
    const modelVariantIndexValue = record['model_variant_index'];
    if (role === 'assistant') {
        const identity = resolveAssistantMessageIdentity({
            assistantTimestamp: timestampValue,
            assistantTurnTimestamp: assistantTurnTimestampValue,
            modelVariantIndex: modelVariantIndexValue
        });
        if (identity === null) {
            return null;
        }
        result.assistantTurnAtMs = identity.assistantTurnTimestamp;
        result.modelVariantIndex = identity.modelVariantIndex;
    } else if (assistantTurnTimestampValue !== undefined || modelVariantIndexValue !== undefined) {
        return null;
    }
    const requestIdRaw = record['request_id'];
    const requestId = optionalTrimmedString(requestIdRaw);
    if (role === 'assistant' && requestId !== null) {
        result.requestId = requestId;
    } else if (requestIdRaw !== undefined && requestIdRaw !== null) {
        return null;
    }
    const promptTokensValue = record['prompt_tokens'];
    const completionTokensValue = record['completion_tokens'];
    const totalTokensValue = record['total_tokens'];
    const hasTokenUsage = (promptTokensValue !== undefined && promptTokensValue !== null) || (completionTokensValue !== undefined && completionTokensValue !== null) || (totalTokensValue !== undefined && totalTokensValue !== null);
    if (hasTokenUsage) {
        if (role !== 'assistant') {
            return null;
        }
        if (!isNonNegativeInteger(promptTokensValue) || !isNonNegativeInteger(completionTokensValue) || !isNonNegativeInteger(totalTokensValue)) {
            return null;
        }
        if (totalTokensValue !== promptTokensValue + completionTokensValue) {
            return null;
        }
        result.promptTokens = promptTokensValue;
        result.completionTokens = completionTokensValue;
        result.totalTokens = totalTokensValue;
    }
    const usageSourceRaw = record['usage_source'];
    const usageSource = optionalTrimmedString(usageSourceRaw);
    if (role === 'assistant' && usageSource !== null) {
        result.usageSource = usageSource;
    } else if (usageSourceRaw !== undefined && usageSourceRaw !== null) {
        return null;
    }
    if (hasTokenUsage && (requestId === null || usageSource === null)) {
        return null;
    }
    const generationLatencyMsValue = record['generation_latency_ms'];
    if (isNumber(generationLatencyMsValue)) {
        result.generationLatencyMs = generationLatencyMsValue;
    }
    const finishReasonValue = record['finish_reason'];
    if (isString(finishReasonValue) && finishReasonValue.trim()) {
        result.finishReason = finishReasonValue.trim();
    }
    const thinkingTailDurationMsValue = record['thinking_tail_duration_ms'];
    if (isNumber(thinkingTailDurationMsValue) && Number.isFinite(thinkingTailDurationMsValue) && Number.isInteger(thinkingTailDurationMsValue) && thinkingTailDurationMsValue >= 0) {
        result.thinkingTailDurationMs = thinkingTailDurationMsValue;
    }
    return result;
};

export { normalizeChatMessageForApi };
