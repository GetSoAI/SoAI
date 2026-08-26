/* SoAI - Manual compaction assistant placeholder insertion [frontend/assets/ts/features/chat/agent/agentCompactionPlaceholder.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isPlainObject } from '@core/typeGuards.ts';
import { createInitialAssistantMessage } from '@features/chat/chatstreamservice/assistantMessageFactory.ts';
import type { AgentCheckpointResponse } from '@core/api/contracts/chatAgentContracts.ts';
import { resolveAssistantMessageTarget } from '@features/chat/agent/agentMessageTargetResolution.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';

const ensureManualCompactionAssistantPlaceholder = (conversation: ConversationContract, checkpoint: AgentCheckpointResponse): boolean => {
    const activity = checkpoint.activities[0];
    if (!isPlainObject(activity)) {
        return false;
    }
    const messageIndex = activity['message_index'];
    if (!isNumber(messageIndex) || !Number.isInteger(messageIndex) || messageIndex < 0) {
        return false;
    }
    const target = resolveAssistantMessageTarget(conversation.messages, messageIndex);
    if (target.status === 'resolved') {
        return false;
    }
    if (target.status === 'invalid') {
        throw new Error(target.reason);
    }
    conversation.messages.push(
        createInitialAssistantMessage({
            assistantTimestamp: checkpoint.startedAtMs,
            assistantTurnTimestamp: checkpoint.startedAtMs,
            model: checkpoint.requestedModel,
            modelVariantIndex: 0,
            requestId: ''
        })
    );
    return true;
};

export { ensureManualCompactionAssistantPlaceholder };
