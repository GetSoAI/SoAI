/* SoAI - Frontend agent event base decoding [frontend/assets/ts/core/realtime/eventcontracts/agentparsing/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import { readNumber, readString } from '@core/types/payloadValueReaders.ts';
import type { AgentPlanStepStatus } from '@core/chat/agentTypes.ts';
import { toTrimmedString } from '@core/normalize.ts';

interface AgentEventBase {
    userId: number;
    convId: string;
    turnId: string;
    iterationIndex: number;
    sequence: number;
    eventType: string;
    status: string;
}

interface AgentItemEventBase extends AgentEventBase {
    itemId: string;
}

const readAgentEventBase = (data: JsonValue): AgentEventBase | null => {
    if (!isObject(data)) {
        return null;
    }
    const userId = readNumber(data, 'user_id');
    const convId = readString(data, 'conv_id');
    const turnId = readString(data, 'turn_id');
    const iterationIndex = readNumber(data, 'iteration_index');
    const sequence = readNumber(data, 'sequence');
    const eventType = readString(data, 'event_type');
    const status = readString(data, 'status');
    const normalizedConvId = toTrimmedString(convId);
    const normalizedTurnId = turnId?.trim() ?? '';
    const normalizedEventType = eventType?.trim() ?? '';
    const normalizedStatus = status?.trim() ?? '';
    if (userId === null || !Number.isInteger(userId) || userId <= 0 || !normalizedConvId || !normalizedTurnId || iterationIndex === null || !Number.isInteger(iterationIndex) || iterationIndex < 0 || sequence === null || !Number.isInteger(sequence) || sequence < 0 || !normalizedEventType || !normalizedStatus) {
        return null;
    }
    return {
        userId,
        convId: normalizedConvId,
        turnId: normalizedTurnId,
        iterationIndex,
        sequence,
        eventType: normalizedEventType,
        status: normalizedStatus
    };
};

const readAgentItemEventBase = (data: JsonValue): AgentItemEventBase | null => {
    const base = readAgentEventBase(data);
    if (!base || !isObject(data)) {
        return null;
    }
    const itemId = readString(data, 'item_id');
    const normalizedItemId = itemId?.trim() ?? '';
    if (!normalizedItemId) {
        return null;
    }
    return {
        ...base,
        itemId: normalizedItemId
    };
};

const VALID_AGENT_PLAN_STEP_STATUSES: ReadonlySet<string> = new Set<string>(['pending', 'in_progress', 'completed']);

const isAgentPlanStepStatus = (value: string): value is AgentPlanStepStatus => VALID_AGENT_PLAN_STEP_STATUSES.has(value);

const parseAgentTodoItems = (data: Record<string, JsonValue | null | undefined>): Array<{ step: string; status: AgentPlanStepStatus }> | null => {
    const todoRaw = data['todo'];
    if (!isArray(todoRaw)) {
        return null;
    }
    const todo: Array<{ step: string; status: AgentPlanStepStatus }> = [];
    for (const entry of todoRaw) {
        if (!isObject(entry)) {
            return null;
        }
        const step = readString(entry, 'step');
        const status = readString(entry, 'status');
        if (step === null || status === null || !isAgentPlanStepStatus(status)) {
            return null;
        }
        todo.push({ step, status });
    }
    return todo;
};

export { parseAgentTodoItems, readAgentEventBase, readAgentItemEventBase };
export type { AgentEventBase, AgentItemEventBase };
