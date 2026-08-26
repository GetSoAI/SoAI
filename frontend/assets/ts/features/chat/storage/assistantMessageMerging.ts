/* SoAI - Chat feature assistant message merging [frontend/assets/ts/features/chat/storage/assistantMessageMerging.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber } from '@core/typeGuards.ts';
import { hasRunningLoadingActivityFromMessage, hasTerminalThinkingActivityStatusRegression } from '@features/chat/assistanteventtimeline/activityState.ts';
import { preserveAssistantCollapsedOverrideRecords } from '@features/chat/assistanteventtimeline/collapsedOverrideRecords.ts';
import type { ChatMessage, ConversationMessage, ToolActivityStatus } from '@features/chat/ChatTypes.ts';
import { resolveAssistantTimelineProgress } from '@features/chat/chatstreamservice/assistantStreamMessageState.ts';
import { hasManualContextCompactionBoundaryMarker } from '@features/chat/message/contextcompaction/detection.ts';
import { buildAssistantVariantIdentityKey, collectAssistantToolCallIds, shareAssistantSemanticIdentity, shareResolvedAssistantVariantIdentity } from '@features/chat/message/assistantMessageIdentity.ts';
import { resolveDurableAssistantTerminalState } from '@features/chat/message/assistantTerminalState.ts';
import { hasPersistedMessageId } from '@features/chat/message/persistedMessageIdentity.ts';
import { isEmptyAssistantPlaceholderMessage } from '@features/chat/message/placeholderAssistantMessage.ts';
import { insertMessageByTimestamp } from '@features/chat/message/messageTimestampOrdering.ts';
import type { ChatStorageMessageRecord } from '@features/chat/storage/storageModels.ts';
import { resolveToolActivityStatusRank } from '@features/chat/toolactivity/toolActivityStatus.ts';

const resolveNonNegativeIntegerMetric = (value: number | undefined): number | null => {
    if (!isNumber(value) || !Number.isFinite(value) || !Number.isInteger(value) || value < 0) {
        return null;
    }
    return value;
};

const resolveAssistantToolStatus = (message: ConversationMessage, expectedCallId: string): ToolActivityStatus | null => {
    const timeline = message.assistantEventTimeline;
    if (!timeline || timeline.length === 0) {
        return null;
    }
    let resolved: ToolActivityStatus | null = null;
    for (const entry of timeline) {
        const tool = entry.payload.tool;
        if (tool === undefined) {
            continue;
        }
        if (tool.callId !== expectedCallId) {
            continue;
        }
        resolved = tool.status;
    }
    return resolved;
};

const isActiveNonTerminalAssistantMessage = (existing: ConversationMessage, activeAssistantMessage: ChatMessage | null): boolean => {
    if (activeAssistantMessage === null || resolveDurableAssistantTerminalState(activeAssistantMessage) !== null) {
        return false;
    }
    return existing === activeAssistantMessage || shareResolvedAssistantVariantIdentity(existing, activeAssistantMessage);
};

const isLocalTerminalAssistantMessage = (existing: ConversationMessage): boolean => {
    return !hasPersistedMessageId(existing) && resolveDurableAssistantTerminalState(existing) !== null;
};

const isEmptyAssistantPlaceholderRecord = (message: ConversationMessage): boolean => {
    return isEmptyAssistantPlaceholderMessage(message);
};

const shouldTrackLocalAssistantForMerge = (existing: ConversationMessage, activeAssistantMessage: ChatMessage | null): boolean => {
    return hasPersistedMessageId(existing) || hasRunningLoadingActivityFromMessage(existing) || isActiveNonTerminalAssistantMessage(existing, activeAssistantMessage) || isLocalTerminalAssistantMessage(existing);
};

const shouldPreserveStreamingAssistantMessage = (existing: ConversationMessage, incoming: ChatStorageMessageRecord, activeAssistantMessage: ChatMessage | null): boolean => {
    if (hasManualContextCompactionBoundaryMarker(incoming)) {
        return false;
    }
    if (hasTerminalThinkingActivityStatusRegression(existing, incoming)) {
        return true;
    }
    if (!hasPersistedMessageId(existing) && hasPersistedMessageId(incoming)) {
        return false;
    }
    const incomingTerminalState = resolveDurableAssistantTerminalState(incoming);
    const existingTerminalState = resolveDurableAssistantTerminalState(existing);
    if (incomingTerminalState !== null && existingTerminalState === null) {
        return false;
    }
    const existingToolCallIds = collectAssistantToolCallIds(existing);
    const incomingToolCallIds = collectAssistantToolCallIds(incoming);
    const sharedToolCallId = incomingToolCallIds.find((callId) => existingToolCallIds.includes(callId)) ?? null;
    if (sharedToolCallId !== null) {
        const existingStatus = resolveAssistantToolStatus(existing, sharedToolCallId);
        const incomingStatus = resolveAssistantToolStatus(incoming, sharedToolCallId);
        if (existingStatus !== null && incomingStatus !== null) {
            const existingStatusRank = resolveToolActivityStatusRank(existingStatus);
            const incomingStatusRank = resolveToolActivityStatusRank(incomingStatus);
            if (incomingStatusRank > existingStatusRank) {
                return false;
            }
            if (incomingStatusRank < existingStatusRank) {
                return true;
            }
        }
    }
    const existingProgress = resolveAssistantTimelineProgress(existing);
    const incomingProgress = resolveAssistantTimelineProgress(incoming);
    if (existingProgress.assistantRevision > incomingProgress.assistantRevision) {
        return true;
    }
    const existingGenerationLatencyMs = resolveNonNegativeIntegerMetric(existing.generationLatencyMs);
    const incomingGenerationLatencyMs = resolveNonNegativeIntegerMetric(incoming.generationLatencyMs);
    if (existingGenerationLatencyMs !== null && (incomingGenerationLatencyMs === null || existingGenerationLatencyMs > incomingGenerationLatencyMs)) {
        return true;
    }
    if (isActiveNonTerminalAssistantMessage(existing, activeAssistantMessage)) {
        if (isEmptyAssistantPlaceholderRecord(existing) && !isEmptyAssistantPlaceholderRecord(incoming)) {
            return false;
        }
        return true;
    }
    return false;
};

const containsAssistantSemanticMessage = (messages: ConversationMessage[], candidate: ConversationMessage): boolean => {
    const candidateVariantKey = buildAssistantVariantIdentityKey(candidate, 'Assistant message merge');
    return messages.some((message) => {
        if (message.role !== 'assistant') {
            return false;
        }
        if (buildAssistantVariantIdentityKey(message, 'Assistant message merge') === candidateVariantKey) {
            return true;
        }
        return shareAssistantSemanticIdentity(message, candidate, 'Assistant message merge');
    });
};

const resolveLocalMessagesForAssistantMerge = (currentMessages: ConversationMessage[], activeAssistantMessage: ChatMessage | null): ConversationMessage[] => {
    if (activeAssistantMessage === null || currentMessages.some((message) => message === activeAssistantMessage || shareResolvedAssistantVariantIdentity(message, activeAssistantMessage))) {
        return currentMessages;
    }
    return [...currentMessages, activeAssistantMessage];
};

const mergeStreamingAssistantMessages = (currentMessages: ConversationMessage[], backendMessages: ChatStorageMessageRecord[], activeAssistantMessage: ChatMessage | null = null): ConversationMessage[] => {
    const localMessages = resolveLocalMessagesForAssistantMerge(currentMessages, activeAssistantMessage);
    const existingByVariantIdentity = new Map<string, ConversationMessage>();
    const existingByToolCallId = new Map<string, ConversationMessage>();
    for (const message of localMessages) {
        if (message.role !== 'assistant') {
            continue;
        }
        if (!shouldTrackLocalAssistantForMerge(message, activeAssistantMessage)) {
            continue;
        }
        existingByVariantIdentity.set(buildAssistantVariantIdentityKey(message, 'Assistant message merge'), message);
        for (const toolCallId of collectAssistantToolCallIds(message)) {
            existingByToolCallId.set(toolCallId, message);
        }
    }
    const merged: ConversationMessage[] = backendMessages.map((backendMessage) => {
        if (backendMessage.role !== 'assistant') {
            return backendMessage;
        }
        const identityKey = buildAssistantVariantIdentityKey(backendMessage, 'Assistant message merge');
        let existing = existingByVariantIdentity.get(identityKey);
        if (!existing) {
            for (const toolCallId of collectAssistantToolCallIds(backendMessage)) {
                existing = existingByToolCallId.get(toolCallId);
                if (existing) {
                    break;
                }
            }
        }
        if (!existing) {
            return backendMessage;
        }
        if (shouldPreserveStreamingAssistantMessage(existing, backendMessage, activeAssistantMessage)) {
            return existing;
        }
        preserveAssistantCollapsedOverrideRecords(existing, backendMessage);
        return backendMessage;
    });

    for (const existing of localMessages) {
        if (existing.role !== 'assistant') {
            continue;
        }
        if (!hasRunningLoadingActivityFromMessage(existing) && !isActiveNonTerminalAssistantMessage(existing, activeAssistantMessage) && !isLocalTerminalAssistantMessage(existing)) {
            continue;
        }
        const timestampValue = existing.timestamp;
        if (!isNumber(timestampValue) || !Number.isFinite(timestampValue) || !Number.isInteger(timestampValue)) {
            continue;
        }
        if (containsAssistantSemanticMessage(merged, existing)) {
            continue;
        }
        insertMessageByTimestamp(merged, existing, timestampValue);
    }

    return merged;
};

export { mergeStreamingAssistantMessages };
