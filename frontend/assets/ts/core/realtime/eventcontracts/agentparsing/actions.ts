/* SoAI - Frontend agent action event decoding [frontend/assets/ts/core/realtime/eventcontracts/agentparsing/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject } from '@core/typeGuards.ts';
import { readBoolean, readNumber, readOptionalTrimmedString, readString } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { parseAgentTodoItems, readAgentEventBase } from '@core/realtime/eventcontracts/agentparsing/state.ts';
import { isAgentMode } from '@core/chat/agentMode.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { AgentModeChangedPayload, AgentPlanUpdatedPayload, AgentTodoUpdatedPayload, AgentTurnCompletedPayload, AgentTurnErrorPayload, AgentTurnStartedPayload } from '@core/chat/agentTypes.ts';

const parseAgentTurnStartedPayload = (data: JsonValue): AgentTurnStartedPayload | null => {
    const base = readAgentEventBase(data);
    if (!base || !isObject(data)) {
        return null;
    }
    const mode = readString(data, 'mode');
    const maxIterations = readNumber(data, 'max_iterations');
    if (mode === null || !isAgentMode(mode) || maxIterations === null || !Number.isInteger(maxIterations) || maxIterations <= 0) {
        return null;
    }
    return {
        ...base,
        mode,
        maxIterations,
        itemId: readOptionalTrimmedString(data, 'item_id')
    };
};

const parseAgentTurnCompletedPayload = (data: JsonValue): AgentTurnCompletedPayload | null => {
    const base = readAgentEventBase(data);
    if (!base || !isObject(data)) {
        return null;
    }
    const totalIterations = readNumber(data, 'total_iterations');
    const reachedMaxIterations = readBoolean(data, 'reached_max_iterations');
    if (totalIterations === null || !Number.isInteger(totalIterations) || totalIterations < 0 || reachedMaxIterations === null) {
        return null;
    }
    return {
        ...base,
        totalIterations,
        reachedMaxIterations,
        itemId: readOptionalTrimmedString(data, 'item_id')
    };
};

const parseAgentTurnErrorPayload = (data: JsonValue): AgentTurnErrorPayload | null => {
    const base = readAgentEventBase(data);
    if (!base || !isObject(data)) {
        return null;
    }
    const message = readString(data, 'message');
    const errorType = readString(data, 'error_type');
    if (message === null || errorType === null) {
        return null;
    }
    return {
        ...base,
        message,
        errorType,
        itemId: readOptionalTrimmedString(data, 'item_id')
    };
};

const parseAgentTodoUpdatedPayload = (data: JsonValue): AgentTodoUpdatedPayload | null => {
    const base = readAgentEventBase(data);
    if (!base || !isObject(data)) {
        return null;
    }
    const todo = parseAgentTodoItems(data);
    if (!todo) {
        return null;
    }
    const revision = readNumber(data, 'revision');
    if (revision === null) {
        return null;
    }
    return {
        ...base,
        revision,
        explanation: readOptionalTrimmedString(data, 'explanation'),
        todo,
        itemId: readOptionalTrimmedString(data, 'item_id')
    };
};

const parseAgentPlanUpdatedPayload = (data: JsonValue): AgentPlanUpdatedPayload | null => {
    const base = readAgentEventBase(data);
    if (!base || !isObject(data)) {
        return null;
    }
    const revision = readNumber(data, 'revision');
    if (revision === null) {
        return null;
    }
    const markdown = readString(data, 'markdown');
    if (markdown === null) {
        return null;
    }
    return {
        ...base,
        revision,
        title: readOptionalTrimmedString(data, 'title'),
        markdown,
        itemId: readOptionalTrimmedString(data, 'item_id')
    };
};

const parseAgentModeChangedPayload = (data: JsonValue): AgentModeChangedPayload | null => {
    if (!isObject(data)) {
        return null;
    }
    const userId = readNumber(data, 'user_id');
    const convId = toTrimmedString(readString(data, 'conv_id'));
    const iterationIndex = readNumber(data, 'iteration_index');
    const sequence = readNumber(data, 'sequence');
    const eventType = (readString(data, 'event_type') ?? '').trim();
    const status = (readString(data, 'status') ?? '').trim();
    const mode = readString(data, 'mode');
    const turnId = (readString(data, 'turn_id') ?? '').trim();
    if (userId === null || !Number.isInteger(userId) || userId <= 0 || !convId || iterationIndex === null || !Number.isInteger(iterationIndex) || iterationIndex < 0 || sequence === null || !Number.isInteger(sequence) || sequence < 0 || !eventType || !status || mode === null || !isAgentMode(mode)) {
        return null;
    }
    return {
        userId,
        convId,
        turnId,
        iterationIndex,
        sequence,
        eventType,
        status,
        mode,
        itemId: readOptionalTrimmedString(data, 'item_id')
    };
};

export { parseAgentModeChangedPayload, parseAgentPlanUpdatedPayload, parseAgentTodoUpdatedPayload, parseAgentTurnCompletedPayload, parseAgentTurnErrorPayload, parseAgentTurnStartedPayload };
