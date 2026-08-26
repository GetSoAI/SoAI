/* SoAI - Chat feature MCP elicitation realtime guards [frontend/assets/ts/features/chat/elicitation/mcpElicitationRealtimeGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { TaskCompleteEvent, TaskCreatedEvent } from '@core/realtime/eventcontracts/taskContracts.ts';
import { resolveTaskOperationConversationId } from '@core/tasks/operationPayloads.ts';

type McpElicitationInteractionType = 'ask_user' | 'tool_approval' | 'vault_secret_request';

const parseMcpElicitationTaskCreatedEvent = (event: TaskCreatedEvent, interactionType: McpElicitationInteractionType): { conversationId: string; taskId: string } | null => {
    const taskType = toTrimmedString(event.taskType);
    if (taskType !== 'mcp_elicitation') {
        return null;
    }
    const status = toTrimmedString(event.status);
    if (status !== 'input_required') {
        return null;
    }
    const eventInteractionType = toTrimmedString(event.metadata['interaction_type']);
    if (eventInteractionType !== interactionType) {
        return null;
    }
    const conversationId = resolveTaskOperationConversationId({
        ownerType: event.ownerType,
        ownerId: event.ownerId
    });
    const taskId = toTrimmedString(event.taskId);
    if (!conversationId || !taskId) {
        return null;
    }
    return { conversationId, taskId };
};

const extractTaskCompleteId = (event: TaskCompleteEvent): string | null => event.taskId;

export { extractTaskCompleteId, parseMcpElicitationTaskCreatedEvent };
export type { McpElicitationInteractionType };
