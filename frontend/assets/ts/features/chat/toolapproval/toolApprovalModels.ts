/* SoAI - Chat feature tool approval models [frontend/assets/ts/features/chat/toolapproval/toolApprovalModels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationInteractionEntry, ConversationPendingInteractionResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { isString } from '@core/typeGuards.ts';
import { optionalTrimmedString, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import { parsePendingInteractionEnvelope, parseConversationInputRecord } from '@features/chat/conversationinputs/envelopeParsing.ts';

type ToolApprovalPrompt = {
    taskId: string;
    notificationId: string | null;
    toolName: string;
    toolCallId: string | null;
    toolArguments: string | null;
    createdAtMs: number;
};

type ToolApprovalPendingResponse = {
    conversationId: string;
    prompt: ToolApprovalPrompt | null;
};

function parseToolApprovalPendingResponse(response: ConversationPendingInteractionResponse): ToolApprovalPendingResponse {
    const envelope = parsePendingInteractionEnvelope(response, 'tool_approval');
    if (envelope.interaction === null) {
        return { conversationId: envelope.conversationId, prompt: null };
    }
    return { conversationId: envelope.conversationId, prompt: parseToolApprovalPrompt(envelope.interaction) };
}

function parseToolApprovalPrompt(interaction: ConversationInteractionEntry): ToolApprovalPrompt {
    const prompt = parseConversationInputRecord(interaction, 'tool_approval');
    const payload = prompt.payload;
    const toolName = readRequiredTrimmedString(payload, 'tool_name', 'tool_name');
    const toolCallIdRaw = payload['tool_call_id'];
    const toolCallId = optionalTrimmedString(toolCallIdRaw);
    const toolArgumentsRaw = payload['tool_arguments'];
    const toolArguments = isString(toolArgumentsRaw) ? toolArgumentsRaw : null;
    return { taskId: prompt.taskId, notificationId: prompt.notificationId, toolName, toolCallId, toolArguments, createdAtMs: prompt.createdAtMs };
}

export { parseToolApprovalPendingResponse };
export type { ToolApprovalPendingResponse, ToolApprovalPrompt };
