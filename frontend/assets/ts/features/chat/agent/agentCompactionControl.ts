/* SoAI - Chat feature agent compaction control [frontend/assets/ts/features/chat/agent/agentCompactionControl.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import type { AgentCheckpointResponse } from '@core/api/contracts/chatAgentContracts.ts';
import type { ChatPageApi } from '@features/chat/pagecontracts/types.ts';

type AgentCompactionApi = ChatPageApi;

const startManualCompaction = async (api: AgentCompactionApi, conversationId: string, modelId: string): Promise<AgentCheckpointResponse> => {
    return await api.webui.chat.agent.startCompaction(conversationId, {
        model: modelId
    });
};

const isCompactionConflictError = (error: Error): boolean => {
    if (error instanceof APIError) {
        return error.status === 409;
    }
    return false;
};

export { startManualCompaction, isCompactionConflictError };
export type { AgentCompactionApi };
