/* SoAI - Chat feature assistant header duration DOM sync [frontend/assets/ts/features/chat/stream/assistantHeaderDurationDomSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { resolveInlineActivityDurationLabel, type InlineActivityDurationArguments } from '@features/chat/message/messageview/inlineActivityDuration.ts';
import { syncInlineActivityDurationReserveStyle } from '@features/chat/message/messageview/inlineActivityDurationReserveStyle.ts';
import { isHeaderOwnedDurationNode, resolveHeaderChildren, resolveInlineActivityHeader } from '@features/chat/message/messageview/inlineActivityHeaderChildrenDomOps.ts';

const ASSISTANT_ACTIVITY_SELECTOR = '.message-role-activity.inline-activity';
const INLINE_ACTIVITY_DURATION_CLASS = 'inline-activity-duration';
const ASSISTANT_STARTED_AT_MS_ATTRIBUTE = 'data-assistant-started-at-ms';

type AssistantHeaderDomCacheEntry = {
    activity: HTMLElement;
    header: HTMLElement;
    durationNode: HTMLElement | null;
};

const assistantHeaderDomCache = new WeakMap<HTMLElement, AssistantHeaderDomCacheEntry>();

const removeUnexpectedAssistantHeaderDurationNodes = (header: HTMLElement, assistantDurationNode: HTMLElement | null): void => {
    for (const child of Array.from(header.children)) {
        if (!(child instanceof HTMLElement) || !child.classList.contains(INLINE_ACTIVITY_DURATION_CLASS)) {
            continue;
        }
        if (child === assistantDurationNode) {
            continue;
        }
        child.remove();
    }
};

const resolveAssistantActivityElement = (messageRoot: HTMLElement, cached: AssistantHeaderDomCacheEntry | null, expectedActivity: HTMLElement | null): HTMLElement | null => {
    const cachedActivity = cached?.activity;
    if (expectedActivity !== null && expectedActivity.isConnected && messageRoot.contains(expectedActivity)) {
        return expectedActivity;
    }
    if (cachedActivity && cachedActivity.isConnected && messageRoot.contains(cachedActivity)) {
        return cachedActivity;
    }
    const resolved = dom.resolve(ASSISTANT_ACTIVITY_SELECTOR, messageRoot);
    return resolved instanceof HTMLElement ? resolved : null;
};

const resolveAssistantHeaderDomCacheEntry = (messageRoot: HTMLElement, expectedActivity: HTMLElement | null = null): AssistantHeaderDomCacheEntry | null => {
    const cached = assistantHeaderDomCache.get(messageRoot) ?? null;
    const activity = resolveAssistantActivityElement(messageRoot, cached, expectedActivity);
    if (activity === null) {
        assistantHeaderDomCache.delete(messageRoot);
        return null;
    }
    const cachedHeader = cached?.header;
    const header = cachedHeader && cachedHeader.isConnected && activity.contains(cachedHeader) ? cachedHeader : resolveInlineActivityHeader(activity);
    if (header === null) {
        assistantHeaderDomCache.delete(messageRoot);
        return null;
    }
    const cachedDurationNode = cached?.durationNode;
    const durationNode = cachedDurationNode && cachedDurationNode.isConnected && header.contains(cachedDurationNode) && isHeaderOwnedDurationNode(header, cachedDurationNode) ? cachedDurationNode : resolveHeaderChildren(header).duration;
    removeUnexpectedAssistantHeaderDurationNodes(header, durationNode);
    const nextEntry = {
        activity,
        header,
        durationNode
    };
    assistantHeaderDomCache.set(messageRoot, nextEntry);
    return nextEntry;
};

const syncAssistantHeaderDurationForArguments = (cacheEntry: AssistantHeaderDomCacheEntry, inputArguments: InlineActivityDurationArguments): boolean => {
    const header = cacheEntry.header;
    const durationNode = cacheEntry.durationNode;
    const label = resolveInlineActivityDurationLabel(inputArguments);
    if (label === null) {
        return false;
    }
    if (durationNode !== null) {
        if (durationNode.textContent === label) {
            return syncInlineActivityDurationReserveStyle(durationNode, inputArguments);
        }
        syncInlineActivityDurationReserveStyle(durationNode, inputArguments);
        durationNode.textContent = label;
        return true;
    }
    const createdDuration = header.ownerDocument.createElement('span');
    createdDuration.className = 'inline-activity-duration';
    createdDuration.setAttribute('data-assistant-response-duration', 'true');
    syncInlineActivityDurationReserveStyle(createdDuration, inputArguments);
    createdDuration.textContent = label;
    header.appendChild(createdDuration);
    cacheEntry.durationNode = createdDuration;
    return true;
};

const syncRunningAssistantHeaderDuration = (activity: HTMLElement, nowMs: number): boolean => {
    const messageRoot = activity.closest('.chat-message.assistant');
    if (!(messageRoot instanceof HTMLElement)) {
        return false;
    }
    const cacheEntry = resolveAssistantHeaderDomCacheEntry(messageRoot, activity);
    if (cacheEntry === null || !activity.classList.contains('inline-activity-status-running')) {
        return false;
    }
    const startedAtRaw = activity.getAttribute(ASSISTANT_STARTED_AT_MS_ATTRIBUTE);
    const startedAtMs = startedAtRaw === null ? Number.NaN : Number(startedAtRaw);
    if (!isEpochMsNumber(startedAtMs)) {
        return false;
    }
    return syncAssistantHeaderDurationForArguments(cacheEntry, {
        status: 'running',
        startedAtMs,
        nowMs
    });
};

const removeAssistantHeaderDuration = (activity: HTMLElement): boolean => {
    const messageRoot = activity.closest('.chat-message.assistant');
    if (!(messageRoot instanceof HTMLElement)) {
        return false;
    }
    const cacheEntry = resolveAssistantHeaderDomCacheEntry(messageRoot, activity);
    if (cacheEntry === null || cacheEntry.durationNode === null) {
        return false;
    }
    cacheEntry.durationNode.remove();
    cacheEntry.durationNode = null;
    return true;
};

export { removeAssistantHeaderDuration, syncRunningAssistantHeaderDuration };
