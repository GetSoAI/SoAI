/* SoAI - Canonical assistant preview feedback state for model-visible recovery [frontend/assets/ts/features/chat/contentPreviewFeedbackState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isObject } from '@core/typeGuards.ts';
import type { ChatMessage, ConversationContract, ConversationMessage } from '@features/chat/ChatTypes.ts';
import type { ContentPreviewFeedbackItem, ContentPreviewFeedbackPayload, ContentPreviewFeedbackState } from '@features/chat/contentPreviewContracts.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { resolveAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';

const MAX_CONTENT_PREVIEW_ITEMS = 20;

type CanonicalAssistantMessage = ChatMessage & { timestamp: number; assistantTurnAtMs: number; modelVariantIndex: 0 };

const isCanonicalAssistantMessage = (message: ConversationMessage | null | undefined): message is CanonicalAssistantMessage => {
    if (!message || !isObject(message) || message.role !== 'assistant') {
        return false;
    }
    const identity = resolveAssistantMessageIdentity({
        assistantTimestamp: message.timestamp,
        assistantTurnTimestamp: message.assistantTurnAtMs,
        modelVariantIndex: message.modelVariantIndex
    });
    return identity !== null && identity.modelVariantIndex === 0;
};

const buildFeedbackKey = (item: ContentPreviewFeedbackItem): string => {
    return `${item.referenceType}|${item.target}|${item.status}|${item.reasonCode}`;
};

const normalizeFeedbackItems = (items: readonly ContentPreviewFeedbackItem[]): ContentPreviewFeedbackItem[] => {
    const normalized: ContentPreviewFeedbackItem[] = [];
    const seen = new Set<string>();
    for (const item of items) {
        const target = item.target.trim();
        if (!target) {
            continue;
        }
        const normalizedItem: ContentPreviewFeedbackItem = {
            referenceType: item.referenceType,
            target,
            status: item.status,
            reasonCode: item.reasonCode
        };
        const key = buildFeedbackKey(normalizedItem);
        if (seen.has(key)) {
            continue;
        }
        normalized.push(normalizedItem);
        seen.add(key);
        if (normalized.length >= MAX_CONTENT_PREVIEW_ITEMS) {
            break;
        }
    }
    return normalized;
};

const haveSameFeedbackItems = (left: readonly ContentPreviewFeedbackItem[], right: readonly ContentPreviewFeedbackItem[]): boolean => {
    if (left.length !== right.length) {
        return false;
    }
    for (let index = 0; index < left.length; index += 1) {
        const leftItem = left[index];
        const rightItem = right[index];
        if (!leftItem || !rightItem) {
            return false;
        }
        if (buildFeedbackKey(leftItem) !== buildFeedbackKey(rightItem)) {
            return false;
        }
    }
    return true;
};

const resolveCurrentFeedbackState = (message: ChatMessage): ContentPreviewFeedbackState | null => {
    const state = message.contentPreviewFeedbackState;
    if (!state) {
        return null;
    }
    const stateIdentity = resolveAssistantMessageIdentity({
        assistantTimestamp: state.assistantAtMs,
        assistantTurnTimestamp: state.assistantTurnAtMs,
        modelVariantIndex: 0
    });
    if (stateIdentity === null || stateIdentity.assistantTimestamp !== message.timestamp || stateIdentity.assistantTurnTimestamp !== message.assistantTurnAtMs) {
        return null;
    }
    if (state.pendingForModel !== true && state.pendingForModel !== false) {
        return null;
    }
    const items = normalizeFeedbackItems(state.items);
    if (items.length <= 0 || items.length !== state.items.length) {
        return null;
    }
    return {
        assistantAtMs: stateIdentity.assistantTimestamp,
        assistantTurnAtMs: stateIdentity.assistantTurnTimestamp,
        items,
        pendingForModel: state.pendingForModel
    };
};

const recordContentPreviewFeedback = (message: ConversationMessage | null | undefined, items: readonly ContentPreviewFeedbackItem[]): void => {
    if (!isCanonicalAssistantMessage(message)) {
        return;
    }
    const normalizedItems = normalizeFeedbackItems(items);
    if (normalizedItems.length <= 0) {
        return;
    }
    const existing = resolveCurrentFeedbackState(message);
    const merged = existing ? normalizeFeedbackItems([...existing.items, ...normalizedItems]) : normalizedItems;
    const shouldRemainPending = existing ? existing.pendingForModel || !haveSameFeedbackItems(existing.items, merged) : true;
    const assistantAtTimestamp = message.timestamp;
    const assistantTurnTimestamp = message.assistantTurnAtMs;
    message.contentPreviewFeedbackState = {
        assistantAtMs: assistantAtTimestamp,
        assistantTurnAtMs: assistantTurnTimestamp,
        items: merged,
        pendingForModel: shouldRemainPending
    };
};

const markContentPreviewFeedbackDelivered = (message: ConversationMessage | null | undefined): void => {
    if (!isCanonicalAssistantMessage(message)) {
        return;
    }
    const state = resolveCurrentFeedbackState(message);
    if (state === null) {
        return;
    }
    message.contentPreviewFeedbackState = {
        assistantAtMs: state.assistantAtMs,
        assistantTurnAtMs: state.assistantTurnAtMs,
        items: [...state.items],
        pendingForModel: false
    };
};

const resolvePendingContentPreviewFeedback = (message: ConversationMessage | null | undefined): ContentPreviewFeedbackPayload | null => {
    if (!isCanonicalAssistantMessage(message)) {
        return null;
    }
    const state = resolveCurrentFeedbackState(message);
    if (state === null || state.pendingForModel !== true || state.items.length <= 0) {
        return null;
    }
    return {
        assistantAtMs: state.assistantAtMs,
        assistantTurnAtMs: state.assistantTurnAtMs,
        items: [...state.items]
    };
};

const resolveLatestPendingContentPreviewFeedback = (conversation: ConversationContract | null | undefined): { message: ChatMessage; feedback: ContentPreviewFeedbackPayload } | null => {
    if (!conversation || !isArray(conversation.messages)) {
        return null;
    }
    for (let index = conversation.messages.length - 1; index >= 0; index -= 1) {
        const candidate = conversation.messages[index];
        if (!isChatMessage(candidate)) {
            continue;
        }
        if (!isCanonicalAssistantMessage(candidate)) {
            continue;
        }
        const feedback = resolvePendingContentPreviewFeedback(candidate);
        return feedback !== null ? { message: candidate, feedback } : null;
    }
    return null;
};

export { isCanonicalAssistantMessage, markContentPreviewFeedbackDelivered, recordContentPreviewFeedback, resolveLatestPendingContentPreviewFeedback, resolvePendingContentPreviewFeedback };
