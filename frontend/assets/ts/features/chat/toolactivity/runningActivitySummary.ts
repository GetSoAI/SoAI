/* SoAI - Chat running activity summary resolution [frontend/assets/ts/features/chat/toolactivity/runningActivitySummary.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { createAssistantTimelineIndexState, type AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { updateAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexUpdate.ts';
import { resolveAssistantTimelineOverlays } from '@features/chat/assistanteventtimeline/timelineIndexResolution.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { hasTerminalAssistantState } from '@features/chat/message/assistantTerminalState.ts';
import { applyToolActivityToRunningCounts, createRunningActivityCounts, resolveCountedRunningActivitySummaryFingerprint, type RunningActivityTarget } from '@features/chat/toolactivity/runningActivitySummaryCounting.ts';

type RunningActivitySummary = {
    activityCount: number;
    backgroundActivityCount: number;
    backgroundSubagentCount: number;
    backgroundTarget: RunningActivityTarget | null;
    nextVisibleAtMs: number | null;
    subagentCount: number;
    target: RunningActivityTarget | null;
    text: string;
};

type RunningActivitySummaryFingerprint = {
    cacheKey: string;
    terminal: boolean;
};

const formatActivityCount = (count: number): string => {
    if (count === 1) {
        return i18n.t('chat.message.runningActivitySummary.activitySingular', { count });
    }
    return i18n.t('chat.message.runningActivitySummary.activityPlural', { count });
};

const formatSubagentCount = (count: number): string => {
    if (count === 1) {
        return i18n.t('chat.message.runningActivitySummary.subagentSingular', { count });
    }
    return i18n.t('chat.message.runningActivitySummary.subagentPlural', { count });
};

const formatBackgroundActivityCount = (count: number): string => {
    if (count === 1) {
        return i18n.t('chat.message.runningActivitySummary.backgroundActivitySingular', { count });
    }
    return i18n.t('chat.message.runningActivitySummary.backgroundActivityPlural', { count });
};

const formatBackgroundSubagentCount = (count: number): string => {
    if (count === 1) {
        return i18n.t('chat.message.runningActivitySummary.backgroundSubagentSingular', { count });
    }
    return i18n.t('chat.message.runningActivitySummary.backgroundSubagentPlural', { count });
};

const formatRunningActivitySummaryText = (activityCount: number, subagentCount: number): string => {
    if (activityCount > 0 && subagentCount > 0) {
        return i18n.t('chat.message.runningActivitySummary.combined', {
            activities: formatActivityCount(activityCount),
            subagents: formatSubagentCount(subagentCount)
        });
    }
    if (activityCount > 0) {
        return formatActivityCount(activityCount);
    }
    if (subagentCount > 0) {
        return formatSubagentCount(subagentCount);
    }
    return '';
};

const formatBackgroundActivitySummaryText = (activityCount: number, subagentCount: number): string => {
    if (activityCount > 0 && subagentCount > 0) {
        return i18n.t('chat.message.runningActivitySummary.backgroundCombined', {
            activities: formatBackgroundActivityCount(activityCount),
            subagents: formatBackgroundSubagentCount(subagentCount)
        });
    }
    if (activityCount > 0) {
        return formatBackgroundActivityCount(activityCount);
    }
    if (subagentCount > 0) {
        return formatBackgroundSubagentCount(subagentCount);
    }
    return '';
};

const resolveRunningActivitySummary = (message: ChatMessage, nowMs: number, timelineIndexState: AssistantTimelineIndexState | null = null, terminalState: boolean | null = null): RunningActivitySummary => {
    const state = timelineIndexState ?? createAssistantTimelineIndexState();
    updateAssistantTimelineIndexState(state, message);
    const overlays = resolveAssistantTimelineOverlays(message, state);
    const counts = createRunningActivityCounts();
    for (const tool of overlays.toolActivity) {
        applyToolActivityToRunningCounts(counts, tool, nowMs);
    }
    const terminal = terminalState ?? hasTerminalAssistantState(message);
    const activityCount = terminal ? 0 : counts.activityCount;
    const subagentCount = terminal ? 0 : counts.subagentCount;
    const backgroundActivityCount = terminal ? counts.activityCount : 0;
    const backgroundSubagentCount = terminal ? counts.subagentCount : 0;
    const text = terminal ? formatBackgroundActivitySummaryText(backgroundActivityCount, backgroundSubagentCount) : formatRunningActivitySummaryText(activityCount, subagentCount);
    return {
        activityCount,
        backgroundActivityCount,
        backgroundSubagentCount,
        backgroundTarget: terminal ? counts.target : null,
        nextVisibleAtMs: counts.nextVisibleAtMs,
        subagentCount,
        target: terminal ? null : counts.target,
        text
    };
};

const resolveRunningActivitySummaryFingerprint = (message: ChatMessage): RunningActivitySummaryFingerprint | null => {
    const fingerprint = resolveCountedRunningActivitySummaryFingerprint(message);
    if (fingerprint === null) {
        return null;
    }
    const terminal = hasTerminalAssistantState(message);
    return {
        cacheKey: `${terminal ? 'terminal' : 'stream'}|${fingerprint}`,
        terminal
    };
};

export { formatBackgroundActivitySummaryText, formatRunningActivitySummaryText, resolveRunningActivitySummary, resolveRunningActivitySummaryFingerprint };
export type { RunningActivitySummary, RunningActivityTarget };
