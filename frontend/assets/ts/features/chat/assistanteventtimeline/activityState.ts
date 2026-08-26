/* SoAI - Chat feature activity state [frontend/assets/ts/features/chat/assistanteventtimeline/activityState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantEventTimelineItem, ConversationMessage, ThinkingTimelineItem } from '@features/chat/ChatTypes.ts';
import type { AssistantActivityState, AssistantActivityStatus } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';

const resolveLatestAssistantActivity = (timeline: readonly AssistantEventTimelineItem[] | null | undefined, eventType: 'loading_activity' | 'processing_activity', fieldName: 'loadingActivity' | 'processingActivity'): AssistantActivityState | null => {
    if (!timeline || timeline.length === 0) {
        return null;
    }
    let latest: AssistantActivityState | null = null;
    for (const event of timeline) {
        const eventTypeValue = event.eventType;
        if (eventTypeValue !== eventType) {
            continue;
        }
        const payload = event.payload[fieldName];
        if (payload !== undefined) latest = payload;
    }
    return latest;
};

const resolveLatestLoadingActivityFromTimeline = (timeline: readonly AssistantEventTimelineItem[] | null | undefined): AssistantActivityState | null => resolveLatestAssistantActivity(timeline, 'loading_activity', 'loadingActivity');

const resolveLatestProcessingActivityFromTimeline = (timeline: readonly AssistantEventTimelineItem[] | null | undefined): AssistantActivityState | null => resolveLatestAssistantActivity(timeline, 'processing_activity', 'processingActivity');

const resolveLatestLoadingActivityFromMessage = (message: ConversationMessage): AssistantActivityState | null => {
    return resolveLatestLoadingActivityFromTimeline(message.assistantEventTimeline);
};

const hasRunningLoadingActivityFromMessage = (message: ConversationMessage): boolean => {
    const loadingActivity = resolveLatestLoadingActivityFromMessage(message);
    return loadingActivity !== null && loadingActivity.status === 'running';
};

const resolveLoadingDurationMsFromMessage = (message: ConversationMessage): number | null => {
    const loadingActivity = resolveLatestLoadingActivityFromMessage(message);
    if (loadingActivity === null) {
        return null;
    }
    return loadingActivity.durationMs;
};

const isTerminalAssistantActivityStatus = (status: AssistantActivityStatus): boolean => {
    return status === 'completed' || status === 'cancelled' || status === 'error';
};

const resolveThinkingStatusByPhaseId = (message: ConversationMessage): Map<string, ThinkingTimelineItem['status']> => {
    const statuses = new Map<string, ThinkingTimelineItem['status']>();
    for (const event of message.assistantEventTimeline ?? []) {
        const thinkingPhase = event.payload.thinkingPhase;
        if (event.eventType === 'thinking_phase' && thinkingPhase !== undefined) {
            statuses.set(thinkingPhase.phaseId, thinkingPhase.status);
        }
    }
    return statuses;
};

const hasTerminalThinkingActivityStatusRegression = (existing: ConversationMessage, incoming: ConversationMessage): boolean => {
    const incomingStatuses = resolveThinkingStatusByPhaseId(incoming);
    for (const [phaseId, existingStatus] of resolveThinkingStatusByPhaseId(existing)) {
        if (!isTerminalAssistantActivityStatus(existingStatus)) {
            continue;
        }
        const incomingStatus = incomingStatuses.get(phaseId);
        if (incomingStatus === undefined || !isTerminalAssistantActivityStatus(incomingStatus)) {
            return true;
        }
    }
    return false;
};

export { hasRunningLoadingActivityFromMessage, hasTerminalThinkingActivityStatusRegression, isTerminalAssistantActivityStatus, resolveLatestLoadingActivityFromMessage, resolveLatestLoadingActivityFromTimeline, resolveLatestProcessingActivityFromTimeline, resolveLoadingDurationMsFromMessage };
export type { AssistantActivityState, AssistantActivityStatus };
