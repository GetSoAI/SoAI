/* SoAI - Agent checkpoint message range validation [frontend/assets/ts/features/chat/agent/agentCheckpointMessageRange.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseCheckpointActivities } from '@features/chat/agent/agentCheckpointActivities.ts';
import { resolveAssistantMessageTarget } from '@features/chat/agent/agentMessageTargetResolution.ts';
import type { AgentCheckpointResponse } from '@core/api/contracts/chatAgentContracts.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';

const agentCheckpointTargetsConversationMessageRange = (conversation: ConversationContract, checkpoint: AgentCheckpointResponse): boolean => {
    if (checkpoint.convId !== conversation.id) {
        return false;
    }
    const activities = parseCheckpointActivities(checkpoint.activities);
    for (const activity of activities) {
        const target = resolveAssistantMessageTarget(conversation.messages, activity.messageIndex);
        if (target.status === 'invalid') {
            return false;
        }
    }
    return true;
};

export { agentCheckpointTargetsConversationMessageRange };
