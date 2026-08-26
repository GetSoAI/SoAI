/* SoAI - Frontend agent WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/agentContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { parseAgentModeChangedPayload, parseAgentPlanUpdatedPayload, parseAgentTodoUpdatedPayload, parseAgentTurnCompletedPayload, parseAgentTurnErrorPayload, parseAgentTurnStartedPayload } from '@core/realtime/eventcontracts/agentparsing/actions.ts';
import { parseAgentItemCompletedPayload, parseAgentItemDeltaPayload, parseAgentItemStartedPayload, parseAgentToolCallCompletedPayload, parseAgentToolCallCreatedPayload, parseAgentToolCallStartedPayload } from '@core/realtime/eventcontracts/agentparsing/effects.ts';
import { parseAgentSubagentPayload } from '@core/realtime/eventcontracts/agentparsing/subagents.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

const requireDecoded =
    <Payload>(decode: (payload: JsonValue) => Payload | null, label: string) =>
    (payload: JsonValue): Payload => {
        const decoded = decode(payload);
        if (decoded === null) throw new TypeError(`${label} payload is invalid`);
        return decoded;
    };

const decodeSubagent = requireDecoded(parseAgentSubagentPayload, 'Agent subagent event');

const AGENT_EVENT_CONTRACTS = Object.freeze({
    turnStarted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_TURN_STARTED, requireDecoded(parseAgentTurnStartedPayload, 'Agent turn started event')),
    itemStarted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_ITEM_STARTED, requireDecoded(parseAgentItemStartedPayload, 'Agent item started event')),
    itemDelta: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_ITEM_DELTA, requireDecoded(parseAgentItemDeltaPayload, 'Agent item delta event')),
    itemCompleted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_ITEM_COMPLETED, requireDecoded(parseAgentItemCompletedPayload, 'Agent item completed event')),
    toolCallCreated: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.TOOL_CALL_CREATED, requireDecoded(parseAgentToolCallCreatedPayload, 'Tool call created event')),
    toolCallStarted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.TOOL_CALL_STARTED, requireDecoded(parseAgentToolCallStartedPayload, 'Tool call started event')),
    toolCallCompleted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.TOOL_CALL_COMPLETED, requireDecoded(parseAgentToolCallCompletedPayload, 'Tool call completed event')),
    turnCompleted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_TURN_COMPLETED, requireDecoded(parseAgentTurnCompletedPayload, 'Agent turn completed event')),
    turnError: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_TURN_ERROR, requireDecoded(parseAgentTurnErrorPayload, 'Agent turn error event')),
    todoUpdated: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_TODO_UPDATED, requireDecoded(parseAgentTodoUpdatedPayload, 'Agent todo updated event')),
    planUpdated: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_PLAN_UPDATED, requireDecoded(parseAgentPlanUpdatedPayload, 'Agent plan updated event')),
    modeChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_MODE_CHANGED, requireDecoded(parseAgentModeChangedPayload, 'Agent mode changed event')),
    subagentSpawned: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_SUBAGENT_SPAWNED, decodeSubagent),
    subagentRunning: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_SUBAGENT_RUNNING, decodeSubagent),
    subagentCompleted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_SUBAGENT_COMPLETED, decodeSubagent),
    subagentMaxIterations: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_SUBAGENT_MAX_ITERATIONS, decodeSubagent),
    subagentError: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_SUBAGENT_ERROR, decodeSubagent),
    subagentAbandoned: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_SUBAGENT_ABANDONED, decodeSubagent),
    subagentCancelled: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.AGENT_SUBAGENT_CANCELLED, decodeSubagent)
});

export { AGENT_EVENT_CONTRACTS };
