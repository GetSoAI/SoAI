/* SoAI - WebUI chat agent API endpoint factory [frontend/assets/ts/core/api/endpoints/webuiChatAgentEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeAgentCheckpoint, decodeAgentMessageWrite, decodeAgentPlanState, decodeAgentShellToolStop, decodeAgentTodoState, decodeAgentTurnCancel, serializeAgentCompactionBoundaryRemovalRequest, serializeAgentCompactionRegenerateRequest, serializeAgentCompactionStartRequest, serializeAgentPlanWriteRequest, serializeAgentShellToolStopRequest, serializeAgentTodoWriteRequest, serializeAgentTurnCancelRequest, type AgentCheckpointResponse, type AgentMessageWriteResponse, type AgentPlanStateResponse, type AgentPlanWriteRequest, type AgentShellToolStopResponse, type AgentTodoStateResponse, type AgentTodoWriteRequest, type AgentTurnCancelRequest, type AgentTurnCancelResponse } from '@core/api/contracts/chatAgentContracts.ts';
import type { WebuiConversationPaths } from '@core/api/endpoints/webuiConversationPaths.ts';
import { isNonNegativeInteger, isPositiveInteger } from '@core/typeGuards.ts';

interface WebuiAgentEndpoints {
    cancelTurn(id: string, turnId: string, request: AgentTurnCancelRequest): Promise<AgentTurnCancelResponse>;
    startCompaction(id: string, payload: { model: string }): Promise<AgentCheckpointResponse>;
    regenerateCompaction(id: string, payload: { assistantTurnAtMs: number; clientId: string; clientRequestId: string; expectedLastModifiedAtMs: number }): Promise<AgentCheckpointResponse>;
    removeCompactionBoundary(id: string, payload: { assistantTurnAtMs: number; modelVariantIndex: number; toolCallId: string; expectedLastModifiedAtMs: number }): Promise<AgentMessageWriteResponse>;
    stopShellToolCall(id: string, payload: { assistantTurnAtMs: number; modelVariantIndex: number; toolCallId: string }): Promise<AgentShellToolStopResponse>;
    todoWrite(id: string, payload: AgentTodoWriteRequest): Promise<AgentTodoStateResponse>;
    planWrite(id: string, payload: AgentPlanWriteRequest): Promise<AgentPlanStateResponse>;
}

const createAgentEndpoints = (api: ApiClientContext, paths: WebuiConversationPaths): WebuiAgentEndpoints => {
    return {
        cancelTurn: async (id, turnId, request): Promise<AgentTurnCancelResponse> => decodeAgentTurnCancel(await api.post(paths.agentTurnCancel(id, turnId), serializeAgentTurnCancelRequest(request))),
        startCompaction: async (id, payload): Promise<AgentCheckpointResponse> => {
            const model = payload.model.trim();
            if (!model) {
                throw new Error('webui.chat.agent.startCompaction requires a non-empty model');
            }
            return decodeAgentCheckpoint(await api.post(paths.agentCompactStart(id), serializeAgentCompactionStartRequest(model)));
        },
        regenerateCompaction: async (id, payload): Promise<AgentCheckpointResponse> => {
            if (!Number.isInteger(payload.assistantTurnAtMs) || payload.assistantTurnAtMs <= 0) {
                throw new Error('webui.chat.agent.regenerateCompaction requires a positive assistantTurnAtMs');
            }
            const clientId = payload.clientId.trim();
            const clientRequestId = payload.clientRequestId.trim();
            if (!clientId || !clientRequestId || !isPositiveInteger(payload.expectedLastModifiedAtMs)) {
                throw new Error('webui.chat.agent.regenerateCompaction requires complete request identity and revision');
            }
            return decodeAgentCheckpoint(await api.post(paths.agentCompactRegenerate(id), serializeAgentCompactionRegenerateRequest({ ...payload, clientId, clientRequestId })));
        },
        removeCompactionBoundary: async (id, payload): Promise<AgentMessageWriteResponse> => decodeAgentMessageWrite(await api.post(paths.agentCompactRemoveBoundary(id), serializeAgentCompactionBoundaryRemovalRequest(payload))),
        stopShellToolCall: async (id, payload): Promise<AgentShellToolStopResponse> => {
            if (!isPositiveInteger(payload.assistantTurnAtMs)) {
                throw new Error('webui.chat.agent.stopShellToolCall requires a positive assistantTurnAtMs');
            }
            if (!isNonNegativeInteger(payload.modelVariantIndex)) {
                throw new Error('webui.chat.agent.stopShellToolCall requires a non-negative modelVariantIndex');
            }
            if (!payload.toolCallId.trim()) {
                throw new Error('webui.chat.agent.stopShellToolCall requires a complete tool call identity');
            }
            return decodeAgentShellToolStop(await api.post(paths.agentShellToolStop(id), serializeAgentShellToolStopRequest(payload.assistantTurnAtMs, payload.modelVariantIndex, payload.toolCallId.trim())));
        },
        todoWrite: async (id, payload): Promise<AgentTodoStateResponse> => decodeAgentTodoState(await api.patch(paths.agentTodo(id), serializeAgentTodoWriteRequest(payload))),
        planWrite: async (id, payload): Promise<AgentPlanStateResponse> => decodeAgentPlanState(await api.patch(paths.agentPlan(id), serializeAgentPlanWriteRequest(payload)))
    };
};

export { createAgentEndpoints };
export type { WebuiAgentEndpoints };
