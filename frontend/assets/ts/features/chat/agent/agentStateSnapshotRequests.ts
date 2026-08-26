/* SoAI - Chat feature agent state snapshot requests [frontend/assets/ts/features/chat/agent/agentStateSnapshotRequests.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';
import { decodeAgentCheckpoint, decodeAgentPlanState, decodeAgentTodoState, type AgentCheckpointResponse, type AgentPlanStateResponse, type AgentTodoStateResponse } from '@core/api/contracts/chatAgentContracts.ts';
import { serializeConversationSnapshotRequest } from '@core/api/contracts/chatRealtimeSnapshotContracts.ts';

const AGENT_CHECKPOINT_RESOURCE = 'webui.chat.agent.checkpoint';
const AGENT_PLAN_RESOURCE = 'webui.chat.agent.plan';
const AGENT_TODO_RESOURCE = 'webui.chat.agent.todo';

const readSnapshotData = async (resource: string, conversationId: string): Promise<JsonValue> => {
    return requestWebSocketSnapshotPayload(resource, serializeConversationSnapshotRequest(conversationId));
};

const requestAgentCheckpointSnapshot = async (conversationId: string): Promise<AgentCheckpointResponse | null> => {
    const payload = await readSnapshotData(AGENT_CHECKPOINT_RESOURCE, conversationId);
    if (payload === null) {
        return null;
    }
    const parsed = decodeAgentCheckpoint(payload);
    if (parsed.convId !== conversationId) {
        throw new Error('Agent checkpoint snapshot payload is invalid');
    }
    return parsed;
};

const requestAgentPlanSnapshot = async (conversationId: string): Promise<AgentPlanStateResponse> => {
    const parsed = decodeAgentPlanState(await readSnapshotData(AGENT_PLAN_RESOURCE, conversationId));
    if (parsed.convId !== conversationId) throw new Error('Agent plan snapshot payload is invalid');
    return parsed;
};

const requestAgentTodoSnapshot = async (conversationId: string): Promise<AgentTodoStateResponse> => {
    const parsed = decodeAgentTodoState(await readSnapshotData(AGENT_TODO_RESOURCE, conversationId));
    if (parsed.convId !== conversationId) throw new Error('Agent todo snapshot payload is invalid');
    return parsed;
};

export { requestAgentCheckpointSnapshot, requestAgentPlanSnapshot, requestAgentTodoSnapshot };
