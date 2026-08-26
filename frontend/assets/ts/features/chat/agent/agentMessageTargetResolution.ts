/* SoAI - Chat agent assistant message target resolution [frontend/assets/ts/features/chat/agent/agentMessageTargetResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';

type AgentAssistantMessageTarget = { status: 'resolved'; message: ChatMessage } | { status: 'open' } | { status: 'invalid'; reason: string };

const resolveAssistantMessageTarget = (messages: readonly ChatMessage[], messageIndex: number): AgentAssistantMessageTarget => {
    if (!Number.isInteger(messageIndex) || messageIndex < 0) {
        return { status: 'invalid', reason: 'Agent turn message_index must be a non-negative integer' };
    }
    let logicalIndex = 0;
    for (const entry of messages) {
        if (entry.role === 'system') {
            continue;
        }
        if (entry.role === 'assistant') {
            if (entry.modelVariantIndex !== 0) {
                continue;
            }
            if (logicalIndex === messageIndex) {
                return { status: 'resolved', message: entry };
            }
            logicalIndex += 1;
            continue;
        }
        if (logicalIndex === messageIndex) {
            return { status: 'invalid', reason: 'Agent turn message_index targets a non-assistant message' };
        }
        logicalIndex += 1;
    }
    return { status: 'open' };
};

const resolveAssistantMessageByLogicalIndex = (messages: readonly ChatMessage[], messageIndex: number): ChatMessage | null => {
    const target = resolveAssistantMessageTarget(messages, messageIndex);
    if (target.status === 'invalid') {
        throw new Error(target.reason);
    }
    if (target.status === 'open') {
        return null;
    }
    return target.message;
};

const canResolveAssistantMessageByLogicalIndex = (messages: readonly ChatMessage[], messageIndex: number): boolean => {
    return resolveAssistantMessageTarget(messages, messageIndex).status !== 'invalid';
};

export { canResolveAssistantMessageByLogicalIndex, resolveAssistantMessageByLogicalIndex, resolveAssistantMessageTarget };
export type { AgentAssistantMessageTarget };
