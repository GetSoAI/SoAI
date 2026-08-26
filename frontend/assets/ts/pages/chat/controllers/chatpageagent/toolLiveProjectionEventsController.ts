/* SoAI - Tool call live projection event parsing and application for chat agent turns [frontend/assets/ts/pages/chat/controllers/chatpageagent/toolLiveProjectionEventsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ToolCallLiveUpdatedEvent } from '@core/realtime/eventcontracts/toolLiveContracts.ts';
import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';
import { serializeToolCallSnapshotRequest } from '@core/api/contracts/chatRealtimeSnapshotContracts.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { canApplyToolCallProjectionWithoutSequenceGap, findAssistantMessageByTimestamp, findToolProjectionByCallId, mapAssistantTimelineToolPayload, mapDecodedAssistantTimelineTool, toolRunningResultIsDetailHydrated, upsertToolCallProjection, type ChatMessage, type ToolActivityItem } from '@features/chat/public.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import type { PendingToolLiveProjectionEvent } from '@pages/chat/controllers/chatpageagent/state.ts';

interface ToolCallLiveUpdatedPayload {
    convId: string;
    assistantAtMs: number;
    assistantTurnAtMs: number;
    modelVariantIndex: number;
    callId: string;
    liveSequence: number;
    liveRevision: number;
    lastLiveEventAtMs: number;
    tool: ToolActivityItem;
}

type ToolCallLiveProjectionApplyResult = 'none' | 'queued' | 'updated';
type ToolCallLiveProjectionApplyOptions = {
    isDisposed(): boolean;
    pendingEvents?: Map<string, PendingToolLiveProjectionEvent>;
    queueIfMissing?: boolean;
    queuedAtMs?: number;
};

const PENDING_TOOL_LIVE_EVENT_TTL_MS = 300000;
const PENDING_TOOL_LIVE_EVENT_LIMIT = 128;
const omitDetailHydratedActiveProjectionResult = (tool: ToolActivityItem): ToolActivityItem => {
    if ((tool.status !== 'pending' && tool.status !== 'running') || !toolRunningResultIsDetailHydrated(tool.toolName)) {
        return tool;
    }
    const nextTool = { ...tool };
    delete nextTool.result;
    return nextTool;
};

const parseToolCallLiveUpdatedPayload = (value: ToolCallLiveUpdatedEvent): ToolCallLiveUpdatedPayload | null => {
    const tool = mapDecodedAssistantTimelineTool(value.tool);
    const normalizedCallId = value.callId;
    const lightweightTool = omitDetailHydratedActiveProjectionResult(tool);
    if (lightweightTool.callId !== normalizedCallId || lightweightTool.liveRevision !== value.liveRevision || lightweightTool.lastLiveSequence !== value.liveSequence || lightweightTool.lastLiveEventAtMs !== value.lastLiveEventAtMs) {
        return null;
    }
    return {
        convId: value.convId,
        assistantAtMs: value.assistantAtMs,
        assistantTurnAtMs: value.assistantTurnAtMs,
        modelVariantIndex: value.modelVariantIndex,
        callId: normalizedCallId,
        liveSequence: value.liveSequence,
        liveRevision: value.liveRevision,
        lastLiveEventAtMs: value.lastLiveEventAtMs,
        tool: lightweightTool
    };
};

const hasProjectionValuesCaughtUp = (projection: ToolActivityItem, liveSequence: number, liveRevision: number, liveEventAtMs: number): boolean => {
    const projectionSequence = projection.lastLiveSequence;
    const projectionRevision = projection.liveRevision;
    const projectionEventAtMs = projection.lastLiveEventAtMs;
    return projectionSequence !== undefined && projectionRevision !== undefined && projectionEventAtMs !== undefined && projectionSequence >= liveSequence && projectionRevision >= liveRevision && projectionEventAtMs >= liveEventAtMs;
};

const hasProjectionCaughtUp = (projection: ToolActivityItem, payload: ToolCallLiveUpdatedPayload): boolean => {
    return hasProjectionValuesCaughtUp(projection, payload.liveSequence, payload.liveRevision, payload.lastLiveEventAtMs);
};

const hasProjectionCaughtUpToTool = (projection: ToolActivityItem, tool: ToolActivityItem): boolean => {
    const liveSequence = tool.lastLiveSequence;
    const liveRevision = tool.liveRevision;
    const liveEventAtMs = tool.lastLiveEventAtMs;
    return liveSequence !== undefined && liveRevision !== undefined && liveEventAtMs !== undefined && hasProjectionValuesCaughtUp(projection, liveSequence, liveRevision, liveEventAtMs);
};

const buildPendingToolLiveProjectionKey = (payload: ToolCallLiveUpdatedPayload): string => {
    return `${payload.convId}:${payload.assistantAtMs}:${payload.assistantTurnAtMs}:${payload.modelVariantIndex}:${payload.callId}`;
};

const purgePendingToolLiveProjectionEvents = (pendingEvents: Map<string, PendingToolLiveProjectionEvent>, nowMs: number): void => {
    for (const [key, record] of pendingEvents.entries()) {
        if (nowMs - record.receivedAtMs > PENDING_TOOL_LIVE_EVENT_TTL_MS) {
            pendingEvents.delete(key);
        }
    }
    while (pendingEvents.size > PENDING_TOOL_LIVE_EVENT_LIMIT) {
        const oldestKey = pendingEvents.keys().next().value;
        if (!isString(oldestKey)) {
            return;
        }
        pendingEvents.delete(oldestKey);
    }
};

const queuePendingToolLiveProjectionEvent = (pendingEvents: Map<string, PendingToolLiveProjectionEvent> | undefined, payload: ToolCallLiveUpdatedPayload, value: ToolCallLiveUpdatedEvent, queuedAtMs: number | undefined): ToolCallLiveProjectionApplyResult => {
    if (pendingEvents === undefined) {
        return 'none';
    }
    const nowMs = monotonicMs();
    const receivedAtMs = queuedAtMs ?? nowMs;
    purgePendingToolLiveProjectionEvents(pendingEvents, nowMs);
    const key = buildPendingToolLiveProjectionKey(payload);
    const existing = pendingEvents.get(key);
    if (existing !== undefined) {
        const existingPayload = parseToolCallLiveUpdatedPayload(existing.value);
        if (existingPayload !== null && hasProjectionCaughtUp(existingPayload.tool, payload)) {
            return 'queued';
        }
    }
    pendingEvents.set(key, { value, receivedAtMs });
    purgePendingToolLiveProjectionEvents(pendingEvents, nowMs);
    return 'queued';
};

const requestProjectionResync = async (payload: ToolCallLiveUpdatedPayload): Promise<ToolActivityItem | null> => {
    const snapshotPayload = await requestWebSocketSnapshotPayload(
        'webui.chat.tool_calls.by_call_id',
        serializeToolCallSnapshotRequest({
            conversationId: payload.convId,
            callId: payload.callId,
            assistantTurnAtMs: payload.assistantTurnAtMs,
            modelVariantIndex: payload.modelVariantIndex
        })
    );
    const mapped = mapAssistantTimelineToolPayload(snapshotPayload);
    if (mapped === null || mapped.callId !== payload.callId) {
        return null;
    }
    if (!hasProjectionCaughtUp(mapped, payload)) {
        return null;
    }
    return omitDetailHydratedActiveProjectionResult(mapped);
};

const requestProjectionResyncNoncritical = async (payload: ToolCallLiveUpdatedPayload): Promise<ToolActivityItem | null> => {
    try {
        return await requestProjectionResync(payload);
    } catch (error) {
        errorHandler.warn('ChatPageAgent', 'Failed to resync tool live projection', ensureError(error));
        return null;
    }
};

const resolveLiveProjectionMessage = (host: ChatPageAgentHost, payload: ToolCallLiveUpdatedPayload): ChatMessage | null => {
    const conversation = host.conversation.getConversationById(payload.convId);
    if (!conversation) {
        return null;
    }
    return findAssistantMessageByTimestamp(conversation.messages, payload.assistantAtMs);
};

const queueMissingLiveProjectionTarget = (options: ToolCallLiveProjectionApplyOptions | undefined, payload: ToolCallLiveUpdatedPayload, value: ToolCallLiveUpdatedEvent): ToolCallLiveProjectionApplyResult => {
    return options?.queueIfMissing === false ? 'none' : queuePendingToolLiveProjectionEvent(options?.pendingEvents, payload, value, options?.queuedAtMs);
};

const applyToolCallLiveProjectionEvent = async (host: ChatPageAgentHost, value: ToolCallLiveUpdatedEvent, options?: ToolCallLiveProjectionApplyOptions): Promise<ToolCallLiveProjectionApplyResult> => {
    if (options?.isDisposed()) {
        return 'none';
    }
    const payload = parseToolCallLiveUpdatedPayload(value);
    if (payload === null) {
        throw new Error(i18n.t('chat.agent.toolLiveInvalidPayload'));
    }
    let message = resolveLiveProjectionMessage(host, payload);
    if (message === null) {
        return queueMissingLiveProjectionTarget(options, payload, value);
    }
    if (!canApplyToolCallProjectionWithoutSequenceGap(message, payload.tool)) {
        return queueMissingLiveProjectionTarget(options, payload, value);
    }
    const existing = findToolProjectionByCallId(message, payload.callId);
    const previousSequence = existing?.lastLiveSequence;
    const hasSequenceGap = previousSequence === undefined ? payload.liveSequence > 0 : payload.liveSequence !== previousSequence + 1;
    let changed = false;
    if (hasSequenceGap) {
        payload.tool.syncStatus = 'out_of_sync';
        changed = upsertToolCallProjection(message, payload.tool);
        const resynced = await requestProjectionResyncNoncritical(payload);
        if (options?.isDisposed()) {
            return 'none';
        }
        message = resolveLiveProjectionMessage(host, payload);
        if (message === null) {
            return queueMissingLiveProjectionTarget(options, payload, value);
        }
        if (resynced !== null) {
            resynced.syncStatus = 'in_sync';
            const current = findToolProjectionByCallId(message, payload.callId);
            if ((current === null || !hasProjectionCaughtUpToTool(current, resynced)) && canApplyToolCallProjectionWithoutSequenceGap(message, resynced)) {
                changed = upsertToolCallProjection(message, resynced) || changed;
            }
        }
    } else {
        payload.tool.syncStatus = 'in_sync';
        changed = upsertToolCallProjection(message, payload.tool);
    }
    if (!changed) {
        return 'none';
    }
    if (options?.isDisposed()) {
        return 'none';
    }
    host.rendering.messages.invalidateMessageProjectionCache(message);
    if (host.conversation.getCurrentConversationId() === payload.convId) {
        if (host.conversation.isChatStreamingConversation(payload.convId)) {
            host.rendering.scheduleStreamingTimelineRender(payload.convId, message);
            return 'updated';
        }
        await host.rendering.scheduleConversationRender();
    }
    return 'updated';
};

const drainPendingToolCallLiveProjectionEvents = async (host: ChatPageAgentHost, pendingEvents: Map<string, PendingToolLiveProjectionEvent>, options?: { isDisposed(): boolean }): Promise<boolean> => {
    let updated = false;
    const entries = Array.from(pendingEvents.entries());
    for (const [key, record] of entries) {
        if (options?.isDisposed()) {
            return updated;
        }
        pendingEvents.delete(key);
        const applied = await applyToolCallLiveProjectionEvent(host, record.value, {
            isDisposed: () => options?.isDisposed() === true,
            pendingEvents,
            queueIfMissing: true,
            queuedAtMs: record.receivedAtMs
        });
        updated = applied === 'updated' || updated;
    }
    return updated;
};

const retainPendingToolCallLiveProjectionEventsForConversation = (pendingEvents: Map<string, PendingToolLiveProjectionEvent>, conversationId: string | null): void => {
    if (conversationId === null) {
        pendingEvents.clear();
        return;
    }
    for (const [key, record] of pendingEvents.entries()) {
        const payload = parseToolCallLiveUpdatedPayload(record.value);
        if (payload === null || payload.convId !== conversationId) {
            pendingEvents.delete(key);
        }
    }
};

export { applyToolCallLiveProjectionEvent, drainPendingToolCallLiveProjectionEvents, retainPendingToolCallLiveProjectionEventsForConversation };
export type { ToolCallLiveProjectionApplyResult };
