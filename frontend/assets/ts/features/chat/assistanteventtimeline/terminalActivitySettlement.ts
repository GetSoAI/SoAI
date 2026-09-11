/* SoAI - Terminal assistant activity projection settlement [frontend/assets/ts/features/chat/assistanteventtimeline/terminalActivitySettlement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantActivityState, AssistantActivityStatus, AssistantTimelineTool } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import type { ChatMessage, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { resolveAssistantTimelineActivitySegments, resolveAssistantTimelineOverlays } from '@features/chat/assistanteventtimeline/timelineIndexResolution.ts';
import { createAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { updateAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexUpdate.ts';
import { isInlineStatusActivitySegment } from '@features/chat/message/inlineStatusActivityIdentity.ts';
import { isDurableBackgroundToolActivity } from '@features/chat/toolactivity/runningActivitySummaryCounting.ts';

type TerminalAssistantStatus = 'complete' | 'cancelled' | 'error';
type SettledActivityStatus = Exclude<AssistantActivityStatus, 'running'>;

const isActiveToolActivity = (tool: ToolActivityItem | AssistantTimelineTool): boolean => tool.status === 'pending' || tool.status === 'running';

const hasUnsettledTerminalAssistantActivities = (message: ChatMessage): boolean => {
    const timelineState = createAssistantTimelineIndexState();
    updateAssistantTimelineIndexState(timelineState, message);
    const hasRunningStatusActivity = resolveAssistantTimelineActivitySegments(timelineState).some((entry) => isInlineStatusActivitySegment(entry.segment) && entry.segment.status === 'running');
    if (hasRunningStatusActivity) return true;
    const overlays = resolveAssistantTimelineOverlays(message, timelineState);
    if (overlays.thinkingTimeline.some((thinkingPhase) => thinkingPhase.status === 'running')) return true;
    return overlays.toolActivity.some((tool) => isActiveToolActivity(tool) && !isDurableBackgroundToolActivity(tool));
};

const resolveSettledStatus = (status: TerminalAssistantStatus): SettledActivityStatus => {
    if (status === 'complete') return 'completed';
    return status;
};

const resolveFrozenDurationMs = (durationMs: number | undefined, startedAtMs: number | undefined, terminalAtMs: number): number | undefined => {
    const suppliedDurationMs = typeof durationMs === 'number' && Number.isFinite(durationMs) && durationMs >= 0 ? durationMs : null;
    if (suppliedDurationMs !== null) return suppliedDurationMs;
    return typeof startedAtMs === 'number' && Number.isFinite(startedAtMs) ? Math.max(0, terminalAtMs - startedAtMs) : undefined;
};

const settleStatusActivity = (activity: AssistantActivityState, status: SettledActivityStatus, terminalAtMs: number): AssistantActivityState => {
    if (activity.status !== 'running') return activity;
    return {
        ...activity,
        status,
        durationMs: resolveFrozenDurationMs(activity.durationMs, activity.startedAtMs, terminalAtMs) ?? 0
    };
};

const settleToolActivity = <Tool extends ToolActivityItem | AssistantTimelineTool>(tool: Tool, status: SettledActivityStatus, terminalAtMs: number): Tool => {
    if (!isActiveToolActivity(tool) || isDurableBackgroundToolActivity(tool)) return tool;
    return {
        ...tool,
        status,
        durationMs: resolveFrozenDurationMs(tool.durationMs, tool.startedAtMs, terminalAtMs),
        completedAtMs: terminalAtMs
    };
};

const settleTerminalAssistantActivities = (message: ChatMessage, terminalStatus: TerminalAssistantStatus, terminalAtMs: number): boolean => {
    const settledStatus = resolveSettledStatus(terminalStatus);
    let timelineChanged = false;
    const timeline = message.assistantEventTimeline?.map((event) => {
        const payload = event.payload;
        const nextPayload = { ...payload };
        let payloadChanged = false;
        if (payload.loadingActivity !== undefined) {
            nextPayload.loadingActivity = settleStatusActivity(payload.loadingActivity, settledStatus, terminalAtMs);
            payloadChanged ||= nextPayload.loadingActivity !== payload.loadingActivity;
        }
        if (payload.processingActivity !== undefined) {
            nextPayload.processingActivity = settleStatusActivity(payload.processingActivity, settledStatus, terminalAtMs);
            payloadChanged ||= nextPayload.processingActivity !== payload.processingActivity;
        }
        if (payload.waitForUserActivity !== undefined) {
            nextPayload.waitForUserActivity = settleStatusActivity(payload.waitForUserActivity, settledStatus, terminalAtMs);
            payloadChanged ||= nextPayload.waitForUserActivity !== payload.waitForUserActivity;
        }
        if (payload.thinkingPhase !== undefined && payload.thinkingPhase.status === 'running') {
            const frozenDurationMs = resolveFrozenDurationMs(payload.thinkingPhase.durationMs, payload.thinkingPhase.startedAtMs, terminalAtMs);
            nextPayload.thinkingPhase = { ...payload.thinkingPhase, status: settledStatus };
            if (frozenDurationMs !== undefined) nextPayload.thinkingPhase.durationMs = frozenDurationMs;
            payloadChanged = true;
        }
        if (payload.tool !== undefined) {
            nextPayload.tool = settleToolActivity(payload.tool, settledStatus, terminalAtMs);
            payloadChanged ||= nextPayload.tool !== payload.tool;
        }
        if (!payloadChanged) return event;
        timelineChanged = true;
        return { ...event, payload: nextPayload };
    });
    let projectionsChanged = false;
    const projections = message.toolCallProjections?.map((tool) => {
        const settledTool = settleToolActivity(tool, settledStatus, terminalAtMs);
        if (settledTool !== tool) projectionsChanged = true;
        return settledTool;
    });
    if (timelineChanged && timeline !== undefined) message.assistantEventTimeline = timeline;
    if (projectionsChanged && projections !== undefined) message.toolCallProjections = projections;
    return timelineChanged || projectionsChanged;
};

export { hasUnsettledTerminalAssistantActivities, settleTerminalAssistantActivities };
export type { TerminalAssistantStatus };
