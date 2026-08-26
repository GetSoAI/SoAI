/* SoAI - Assistant message semantic identity resolution [frontend/assets/ts/features/chat/message/assistantMessageIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage, ConversationMessage } from '@features/chat/ChatTypes.ts';
import { requireAssistantVariantIdentity, resolveAssistantVariantIdentity, type AssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';

const requireAssistantMessageVariantIdentity = (message: ChatMessage, context: string): AssistantVariantIdentity => {
    return requireAssistantVariantIdentity({
        assistantTurnTimestamp: message.assistantTurnAtMs,
        modelVariantIndex: message.modelVariantIndex,
        context
    });
};

const formatAssistantVariantIdentityKey = (identity: AssistantVariantIdentity): string => {
    return `${String(identity.assistantTurnTimestamp)}:${String(identity.modelVariantIndex)}`;
};

const buildAssistantVariantIdentityKey = (message: ChatMessage, context: string): string => {
    const identity = requireAssistantMessageVariantIdentity(message, context);
    return `variant:${formatAssistantVariantIdentityKey(identity)}`;
};

const resolveAssistantVariantMessageIndex = (messages: readonly ConversationMessage[], identity: AssistantVariantIdentity): number | null => {
    for (let index = 0; index < messages.length; index += 1) {
        const message = messages[index];
        if (message?.role === 'assistant' && message.assistantTurnAtMs === identity.assistantTurnTimestamp && message.modelVariantIndex === identity.modelVariantIndex) {
            return index;
        }
    }
    return null;
};

const collectAssistantToolCallIds = (message: ChatMessage): string[] => {
    const timeline = message.assistantEventTimeline;
    if (!timeline || timeline.length === 0) {
        return [];
    }
    const toolCallIds: string[] = [];
    const seen = new Set<string>();
    for (const entry of timeline) {
        const tool = entry.payload.tool;
        if (tool === undefined) {
            continue;
        }
        const callId = tool.callId;
        if (seen.has(callId)) {
            continue;
        }
        seen.add(callId);
        toolCallIds.push(callId);
    }
    return toolCallIds;
};

const resolveAssistantSemanticIdentityKey = (message: ChatMessage, context: string): string => {
    const toolCallIds = collectAssistantToolCallIds(message);
    if (toolCallIds.length > 0) {
        return `tool:${JSON.stringify(toolCallIds)}`;
    }
    return buildAssistantVariantIdentityKey(message, context);
};

const shareAssistantSemanticIdentity = (left: ChatMessage, right: ChatMessage, context: string): boolean => {
    if (buildAssistantVariantIdentityKey(left, context) === buildAssistantVariantIdentityKey(right, context)) {
        return true;
    }
    const leftToolCallIds = collectAssistantToolCallIds(left);
    if (leftToolCallIds.length === 0) {
        return false;
    }
    const rightToolCallIds = collectAssistantToolCallIds(right);
    return rightToolCallIds.some((callId) => leftToolCallIds.includes(callId));
};

const shareResolvedAssistantVariantIdentity = (left: ChatMessage, right: ChatMessage): boolean => {
    const leftIdentity = resolveAssistantVariantIdentity({
        assistantTurnTimestamp: left.assistantTurnAtMs,
        modelVariantIndex: left.modelVariantIndex
    });
    if (leftIdentity === null) {
        return false;
    }
    const rightIdentity = resolveAssistantVariantIdentity({
        assistantTurnTimestamp: right.assistantTurnAtMs,
        modelVariantIndex: right.modelVariantIndex
    });
    if (rightIdentity === null) {
        return false;
    }
    return leftIdentity.assistantTurnTimestamp === rightIdentity.assistantTurnTimestamp && leftIdentity.modelVariantIndex === rightIdentity.modelVariantIndex;
};

export { buildAssistantVariantIdentityKey, collectAssistantToolCallIds, formatAssistantVariantIdentityKey, requireAssistantMessageVariantIdentity, resolveAssistantSemanticIdentityKey, resolveAssistantVariantMessageIndex, shareAssistantSemanticIdentity, shareResolvedAssistantVariantIdentity };
