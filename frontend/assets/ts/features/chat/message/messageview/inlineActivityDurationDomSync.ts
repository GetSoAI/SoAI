/* SoAI - Chat feature inline activity duration DOM sync [frontend/assets/ts/features/chat/message/messageview/inlineActivityDurationDomSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { resolveInlineActivityDurationLabel, type InlineActivityDurationArguments } from '@features/chat/message/messageview/inlineActivityDuration.ts';
import { syncInlineActivityDurationReserveStyle } from '@features/chat/message/messageview/inlineActivityDurationReserveStyle.ts';
import { insertBeforeHeaderActions, isHeaderOwnedDurationNode, resolveHeaderChildren, resolveInlineActivityHeader } from '@features/chat/message/messageview/inlineActivityHeaderChildrenDomOps.ts';
import { resolveInlineToolActivityDurationLabel } from '@features/chat/message/messageview/inlineToolDurationLabel.ts';

const INLINE_TOOL_ACTIVITY_CLASS = 'inline-activity-type-tool';
type InlineActivityDomCacheEntry = {
    header: HTMLElement;
    durationNode: HTMLElement | null;
    actionButton: HTMLElement | null;
};

type InlineActivityDurationSyncResult = {
    hasDuration: boolean;
    updated: boolean;
};

const inlineActivityDomCache = new WeakMap<HTMLElement, InlineActivityDomCacheEntry>();

const resolveStartedAtMs = (activity: Element): number | null => {
    const raw = activity.getAttribute('data-started-at-ms');
    if (!raw) {
        return null;
    }
    const startedAtMs = Number(raw);
    if (!Number.isFinite(startedAtMs) || !Number.isInteger(startedAtMs) || !isEpochMsNumber(startedAtMs)) {
        return null;
    }
    return startedAtMs;
};

const resolveOrCreateDurationNode = (header: HTMLElement): HTMLElement => {
    const children = resolveHeaderChildren(header);
    const existing = children.duration;
    if (existing instanceof HTMLElement) {
        const actionButton = children.stopButton ?? children.closeButton;
        if (actionButton instanceof HTMLElement && existing.nextSibling !== actionButton) {
            header.insertBefore(existing, actionButton);
        }
        return existing;
    }
    const created = header.ownerDocument.createElement('span');
    created.className = 'inline-activity-duration';
    insertBeforeHeaderActions(header, created);
    return created;
};

const resolveInlineActivityDomCacheEntry = (activity: HTMLElement): InlineActivityDomCacheEntry | null => {
    const cached = inlineActivityDomCache.get(activity) ?? null;
    const cachedHeader = cached?.header;
    const header = cachedHeader && cachedHeader.isConnected && activity.contains(cachedHeader) ? cachedHeader : resolveInlineActivityHeader(activity);
    if (header === null) {
        inlineActivityDomCache.delete(activity);
        return null;
    }
    const headerChildren = resolveHeaderChildren(header);
    const actionButton = headerChildren.stopButton ?? headerChildren.closeButton;
    const cachedDurationNode = cached?.durationNode;
    const durationNode = cachedDurationNode && cachedDurationNode.isConnected && header.contains(cachedDurationNode) && isHeaderOwnedDurationNode(header, cachedDurationNode) ? cachedDurationNode : headerChildren.duration;
    const nextEntry = {
        header,
        durationNode,
        actionButton
    };
    inlineActivityDomCache.set(activity, nextEntry);
    return nextEntry;
};

const syncRunningInlineActivityDurationsForActivities = (activities: readonly HTMLElement[], nowMs: number): InlineActivityDurationSyncResult => {
    if (activities.length === 0) {
        return {
            hasDuration: false,
            updated: false
        };
    }
    let hasDuration = false;
    let updated = false;
    for (const activity of activities) {
        const startedAtMs = resolveStartedAtMs(activity);
        if (startedAtMs === null) {
            continue;
        }
        const cacheEntry = resolveInlineActivityDomCacheEntry(activity);
        if (cacheEntry === null) {
            continue;
        }
        const durationArguments = {
            status: 'running',
            startedAtMs,
            nowMs
        };
        const result = syncInlineActivityDurationForArguments(activity, cacheEntry, durationArguments);
        hasDuration ||= result.hasDuration;
        updated ||= result.updated;
    }
    return {
        hasDuration,
        updated
    };
};

const syncInlineActivityDurationForArguments = (activity: HTMLElement, cacheEntry: InlineActivityDomCacheEntry, durationArguments: InlineActivityDurationArguments): InlineActivityDurationSyncResult => {
    const nextLabel = activity.classList.contains(INLINE_TOOL_ACTIVITY_CLASS)
        ? resolveInlineToolActivityDurationLabel({
              status: durationArguments.status === 'running' ? 'running' : 'completed',
              durationMs: durationArguments.durationMs,
              startedAtMs: durationArguments.startedAtMs,
              nowMs: durationArguments.nowMs
          })
        : resolveInlineActivityDurationLabel(durationArguments);
    if (nextLabel === null) {
        return { hasDuration: false, updated: false };
    }
    const header = cacheEntry.header;
    const durationNode = cacheEntry.durationNode && cacheEntry.durationNode.isConnected ? cacheEntry.durationNode : resolveOrCreateDurationNode(header);
    cacheEntry.durationNode = durationNode;
    let updated = false;
    if (cacheEntry.actionButton && cacheEntry.actionButton.isConnected && durationNode.nextSibling !== cacheEntry.actionButton) {
        header.insertBefore(durationNode, cacheEntry.actionButton);
        updated = true;
    }
    if (syncInlineActivityDurationReserveStyle(durationNode, durationArguments)) {
        updated = true;
    }
    if (durationNode.textContent !== nextLabel) {
        durationNode.textContent = nextLabel;
        updated = true;
    }
    return { hasDuration: true, updated };
};

const syncRunningInlineActivityDuration = (activity: HTMLElement, nowMs: number): InlineActivityDurationSyncResult => {
    return syncRunningInlineActivityDurationsForActivities([activity], nowMs);
};

const syncSettledInlineActivityDuration = (activity: HTMLElement, durationMs: number, animateEntrance = false): InlineActivityDurationSyncResult => {
    const cacheEntry = resolveInlineActivityDomCacheEntry(activity);
    if (cacheEntry === null) {
        return { hasDuration: false, updated: false };
    }
    const hadDuration = cacheEntry.durationNode !== null && cacheEntry.durationNode.isConnected;
    const result = syncInlineActivityDurationForArguments(activity, cacheEntry, {
        status: 'completed',
        durationMs
    });
    if (animateEntrance && !hadDuration && cacheEntry.durationNode !== null) {
        cacheEntry.durationNode.classList.add('inline-activity-duration--enter');
    }
    return result;
};

const removeInlineActivityDuration = (activity: HTMLElement): boolean => {
    const cacheEntry = resolveInlineActivityDomCacheEntry(activity);
    if (cacheEntry === null) {
        return false;
    }
    const durationNode = cacheEntry.durationNode;
    if (!(durationNode instanceof HTMLElement) || !durationNode.isConnected) {
        return false;
    }
    durationNode.remove();
    cacheEntry.durationNode = null;
    return true;
};

export { removeInlineActivityDuration, syncRunningInlineActivityDuration, syncSettledInlineActivityDuration };
export type { InlineActivityDurationSyncResult };
