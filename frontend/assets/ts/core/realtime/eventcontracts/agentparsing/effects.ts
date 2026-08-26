/* SoAI - Frontend agent item and tool event decoding [frontend/assets/ts/core/realtime/eventcontracts/agentparsing/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject } from '@core/typeGuards.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { readNumber, readOptionalTrimmedString, readString } from '@core/types/payloadValueReaders.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { parseAgentCodeDiffsFromRecord } from '@core/realtime/eventcontracts/agentparsing/codeDiffs.ts';
import { readAgentItemEventBase } from '@core/realtime/eventcontracts/agentparsing/state.ts';
import type { AgentItemCompletedPayload, AgentItemDeltaPayload, AgentItemStartedPayload, AgentToolCallCompletedPayload, AgentToolCallCreatedPayload, AgentToolCallRunningPayload, AgentToolCallStartedPayload } from '@core/chat/agentTypes.ts';
import { toTrimmedString } from '@core/normalize.ts';

const parseAgentItemStartedPayload = (data: JsonValue): AgentItemStartedPayload | null => {
    const base = readAgentItemEventBase(data);
    if (!base || !isObject(data)) {
        return null;
    }
    const itemType = readString(data, 'item_type');
    if (itemType === null) {
        return null;
    }
    return {
        ...base,
        itemType
    };
};

const parseAgentItemDeltaPayload = (data: JsonValue): AgentItemDeltaPayload | null => {
    const base = readAgentItemEventBase(data);
    if (!base || !isObject(data)) {
        return null;
    }
    const textDelta = readString(data, 'text_delta');
    if (textDelta === null) {
        return null;
    }
    return {
        ...base,
        textDelta
    };
};

const parseAgentItemCompletedPayload = (data: JsonValue): AgentItemCompletedPayload | null => {
    const base = readAgentItemEventBase(data);
    if (!base || !isObject(data)) {
        return null;
    }
    const finalText = readString(data, 'final_text');
    if (finalText === null) {
        return null;
    }
    return {
        ...base,
        finalText
    };
};

type ToolCallEventBase = {
    userId: number;
    convId: string;
    turnId: string;
    iterationIndex: number;
    messageIndex: number;
    sequence: number;
    toolCallId: string;
    toolName: string;
    toolArguments: string | null;
};

const readToolCallEventBase = (data: JsonValue, expectedType: string): ToolCallEventBase | null => {
    if (!isObject(data)) {
        return null;
    }
    const type = readString(data, 'type');
    if (type !== expectedType) {
        return null;
    }
    const userId = readNumber(data, 'user_id');
    const convId = readString(data, 'conv_id');
    const turnId = readString(data, 'turn_id');
    const iterationIndex = readNumber(data, 'iteration_index');
    const messageIndex = readNumber(data, 'message_index');
    const sequenceIndex = readNumber(data, 'sequence_index');
    const callId = readString(data, 'call_id');
    const toolName = readString(data, 'tool_name');
    const normalizedConvId = toTrimmedString(convId);
    const normalizedTurnId = turnId?.trim() ?? '';
    const normalizedToolCallId = callId?.trim() ?? '';
    const normalizedToolName = toolName?.trim() ?? '';
    if (userId === null || !Number.isInteger(userId) || userId <= 0 || !normalizedConvId || !normalizedTurnId || iterationIndex === null || !Number.isInteger(iterationIndex) || iterationIndex < 0 || messageIndex === null || !Number.isInteger(messageIndex) || messageIndex < 0 || sequenceIndex === null || !Number.isInteger(sequenceIndex) || sequenceIndex < 0 || !normalizedToolCallId || !normalizedToolName) {
        return null;
    }
    return {
        userId,
        convId: normalizedConvId,
        turnId: normalizedTurnId,
        iterationIndex,
        messageIndex,
        sequence: sequenceIndex,
        toolCallId: normalizedToolCallId,
        toolName: normalizedToolName,
        toolArguments: readOptionalTrimmedString(data, 'tool_arguments')
    };
};

const parseAgentToolCallCreatedPayload = (data: JsonValue): AgentToolCallCreatedPayload | null => {
    const base = readToolCallEventBase(data, 'ToolCallCreatedEvent');
    if (!base) {
        return null;
    }
    return {
        userId: base.userId,
        convId: base.convId,
        turnId: base.turnId,
        itemId: base.toolCallId,
        iterationIndex: base.iterationIndex,
        messageIndex: base.messageIndex,
        sequence: base.sequence,
        toolCallId: base.toolCallId,
        toolName: base.toolName,
        toolArguments: base.toolArguments,
        eventType: 'item/toolCall/created',
        status: 'pending'
    };
};

const parseAgentToolCallStartedPayload = (data: JsonValue): AgentToolCallStartedPayload | null => {
    const base = readToolCallEventBase(data, 'ToolCallStartedEvent');
    if (!base || !isObject(data)) {
        return null;
    }
    const startedAtMs = readNumber(data, 'started_at_ms');
    if (startedAtMs === null || !Number.isInteger(startedAtMs) || !isEpochMsNumber(startedAtMs)) {
        return null;
    }
    return {
        userId: base.userId,
        convId: base.convId,
        turnId: base.turnId,
        itemId: base.toolCallId,
        iterationIndex: base.iterationIndex,
        messageIndex: base.messageIndex,
        sequence: base.sequence,
        toolCallId: base.toolCallId,
        toolName: base.toolName,
        startedAtMs,
        toolArguments: base.toolArguments,
        eventType: 'item/toolCall/started',
        status: 'running'
    };
};

const parseAgentToolCallRunningPayload = (data: JsonValue): AgentToolCallRunningPayload | null => {
    const base = readAgentItemEventBase(data);
    if (!base || !isObject(data)) {
        return null;
    }
    if (base.status !== 'running' || base.eventType !== 'item/toolCall/running') {
        return null;
    }
    const toolCallId = readString(data, 'tool_call_id');
    const toolName = readString(data, 'tool_name');
    const startedAtMs = readNumber(data, 'started_at_ms');
    const durationMs = readNumber(data, 'duration_ms');
    if (toolCallId === null || toolName === null || startedAtMs === null || !Number.isInteger(startedAtMs) || !isEpochMsNumber(startedAtMs) || durationMs === null || !Number.isInteger(durationMs) || durationMs < 0) {
        return null;
    }
    return {
        ...base,
        toolCallId,
        toolName,
        startedAtMs,
        durationMs,
        status: 'running'
    };
};

const parseAgentToolCallCompletedPayload = (data: JsonValue): AgentToolCallCompletedPayload | null => {
    const base = readToolCallEventBase(data, 'ToolCallCompletedEvent');
    if (!base || !isObject(data)) {
        return null;
    }
    const status = readString(data, 'status');
    if (status === null) {
        return null;
    }
    const normalizedStatus = status.trim();
    if (normalizedStatus !== 'completed' && normalizedStatus !== 'cancelled' && normalizedStatus !== 'error') {
        return null;
    }
    const completionStatus: 'completed' | 'cancelled' | 'error' = normalizedStatus;
    const durationMsRaw = readNumber(data, 'duration_ms');
    const durationMs = durationMsRaw === null ? null : Number.isInteger(durationMsRaw) && durationMsRaw >= 0 ? durationMsRaw : null;
    const errorMessage = readOptionalTrimmedString(data, 'error_message');
    const result = Object.hasOwn(data, 'result') ? (data['result'] ?? null) : errorMessage ? { error: errorMessage } : null;
    return {
        userId: base.userId,
        convId: base.convId,
        turnId: base.turnId,
        itemId: base.toolCallId,
        iterationIndex: base.iterationIndex,
        messageIndex: base.messageIndex,
        sequence: base.sequence,
        toolCallId: base.toolCallId,
        toolName: base.toolName,
        startedAtMs: null,
        durationMs,
        result,
        toolArguments: base.toolArguments,
        codeDiffs: isJsonObject(data) ? parseAgentCodeDiffsFromRecord(data) : null,
        eventType: 'item/toolCall/completed',
        status: completionStatus
    };
};

export { parseAgentItemCompletedPayload, parseAgentItemDeltaPayload, parseAgentItemStartedPayload, parseAgentToolCallCompletedPayload, parseAgentToolCallCreatedPayload, parseAgentToolCallRunningPayload, parseAgentToolCallStartedPayload };
