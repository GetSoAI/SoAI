/* SoAI - Frontend Chat conversation-input envelope parsing [frontend/assets/ts/features/chat/conversationinputs/envelopeParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { ConversationInteractionEntry, ConversationPendingInteractionResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface PendingInteractionEnvelope {
    conversationId: string;
    interaction: ConversationInteractionEntry | null;
}

interface ConversationInputRecord {
    taskId: string;
    notificationId: string | null;
    createdAtMs: number;
    payload: JsonObject;
}

const parsePendingInteractionEnvelope = (response: ConversationPendingInteractionResponse, prefix: string): PendingInteractionEnvelope => {
    const conversationId = response.convId.trim();
    if (!conversationId) {
        throw new Error(`${prefix}.pending.conv_id must be a non-empty string.`);
    }
    return { conversationId, interaction: response.interaction };
};

const parseConversationInputRecord = (interaction: ConversationInteractionEntry, prefix: string): ConversationInputRecord => {
    const createdAtMs = interaction.createdAtMs;
    if (createdAtMs <= 0) {
        throw new Error(`${prefix}.created_at_ms must be a positive number.`);
    }
    return {
        taskId: interaction.taskId,
        notificationId: interaction.notificationId,
        createdAtMs,
        payload: requireRecord(interaction.payload, `${prefix}.payload`)
    };
};

export { parsePendingInteractionEnvelope, parseConversationInputRecord };
