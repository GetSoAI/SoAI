/* SoAI - Canonical refresh-delay resolution for running inline activities [frontend/assets/ts/features/chat/message/activityRefreshDelay.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveInlineActivityDurationArguments, resolveInlineActivityRefreshDelayMs } from '@features/chat/message/messageview/inlineActivityDuration.ts';
import { resolveAssistantHeaderDurationArguments } from '@features/chat/message/messageview/assistantHeaderDuration.ts';
import { CHAT_ACTIVITY_DURATION_REFRESH_INTERVAL_MS } from '@features/chat/chatConstants.ts';
import { isInlineRefreshActivitySegment } from '@features/chat/message/messageSegmentTypes.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';

const earlierRefreshDelayMs = (current: number | null, candidate: number | null): number | null => {
    if (candidate === null) {
        return current;
    }
    if (current === null || candidate < current) {
        return candidate;
    }
    return current;
};

const isDurationRefreshVisible = (segment: MessageSegment, displayMode: ChatActivityDurationDisplayMode): boolean => {
    if (displayMode === 'all') {
        return true;
    }
    return (segment.type === 'inline_tool_activity' || segment.type === 'inline_thinking_activity') && segment.collapsed === false;
};

const resolveRunningInlineActivityRefreshDelayMs = (segments: MessageSegment[], nowMs: number, displayMode: ChatActivityDurationDisplayMode): number | null => {
    let refreshDelayMs: number | null = null;
    for (const segment of segments) {
        if (!segment) {
            continue;
        }
        if (!isInlineRefreshActivitySegment(segment)) {
            continue;
        }
        if (!isDurationRefreshVisible(segment, displayMode)) {
            continue;
        }
        const nextDelayMs = resolveInlineActivityRefreshDelayMs(resolveInlineActivityDurationArguments(segment, nowMs));
        refreshDelayMs = earlierRefreshDelayMs(refreshDelayMs, nextDelayMs);
    }
    return refreshDelayMs;
};

const resolveHasRunningInlineRefreshActivity = (segments: MessageSegment[], nowMs: number): boolean => {
    return resolveRunningInlineActivityRefreshDelayMs(segments, nowMs, 'all') !== null;
};

const canKnownDelayWinWithoutSegments = (refreshDelayMs: number | null): boolean => {
    return refreshDelayMs !== null && refreshDelayMs <= CHAT_ACTIVITY_DURATION_REFRESH_INTERVAL_MS;
};

const resolveRunningActivityRefreshDelayMs = (message: ChatMessage, resolveSegments: () => MessageSegment[], nowMs: number, runningSummaryRefreshDelayMs: number | null, displayMode: ChatActivityDurationDisplayMode): number | null => {
    let refreshDelayMs = runningSummaryRefreshDelayMs;
    const assistantHeaderDurationArguments = displayMode === 'all' ? resolveAssistantHeaderDurationArguments(message, nowMs) : null;
    if (assistantHeaderDurationArguments !== null) {
        const assistantHeaderDelayMs = resolveInlineActivityRefreshDelayMs(assistantHeaderDurationArguments);
        refreshDelayMs = earlierRefreshDelayMs(refreshDelayMs, assistantHeaderDelayMs);
    }
    if (canKnownDelayWinWithoutSegments(refreshDelayMs)) {
        return refreshDelayMs;
    }
    const inlineDelayMs = resolveRunningInlineActivityRefreshDelayMs(resolveSegments(), nowMs, displayMode);
    return earlierRefreshDelayMs(refreshDelayMs, inlineDelayMs);
};

export { resolveHasRunningInlineRefreshActivity, resolveRunningActivityRefreshDelayMs };
