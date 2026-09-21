/* SoAI - Chat feature controller state [frontend/assets/ts/features/chat/chatstreamservice/controller/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { rejectConversationIdleWaiters, resolveConversationIdleWaiters } from '@features/chat/chatstreamservice/controller/idleWaiters.ts';
import { applyStreamingUiTransition, syncCurrentConversationStreamingControls } from '@features/chat/chatstreamservice/controller/streamUiState.ts';
import type { ChatStreamingControllerContext, ChatStreamingControllerDependencies, ChatStreamingControllerOptions, ConversationStreamState, PendingRender, StreamLifecyclePhase } from '@features/chat/chatstreamservice/controller/types.ts';
import { resetConversationTerminalization, resolveAllConversationTerminalizationPromises, resolveConversationTerminalizationPromise } from '@features/chat/chatstreamservice/controller/terminalizationState.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

export function createChatStreamingControllerContext(dependencies: ChatStreamingControllerDependencies, options: ChatStreamingControllerOptions = {}): ChatStreamingControllerContext {
    const resolvedErrorHandler = options.errorHandler === undefined ? null : options.errorHandler;
    return {
        dependencies,
        errorHandler: resolvedErrorHandler,
        scheduleStreamRender: null,
        reconcileActivityDurations: null,
        missingTargetRecoveryConversationId: null,
        isRenderInProgress: false,
        serviceUnsubscribe: null,
        cachedStreamingElements: null,
        streamStateByConversationId: new Map(),
        idleWaitersByConversationId: new Map(),
        requestTokenByConversationId: new Map(),
        timers: new ResourceTracker(),
        presentationActive: true,
        presentationGeneration: 0,
        disposed: false
    };
}

const resolveCurrentConversationId = (context: ChatStreamingControllerContext): string | null => {
    const currentConversationId = normalizeConversationId(context.dependencies.state.getCurrentConversationId());
    if (!currentConversationId) {
        return null;
    }
    return currentConversationId;
};

export function clearActivityRefreshTimer(context: ChatStreamingControllerContext, conversationId: string): void {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return;
    }
    const state = context.streamStateByConversationId.get(normalizedConversationId);
    if (!state || state.activityRefreshTimerId === null) {
        return;
    }
    context.timers.clearTimeout(state.activityRefreshTimerId);
    state.activityRefreshTimerId = null;
}

export function requireScheduleStreamRender(context: ChatStreamingControllerContext): (render: PendingRender) => void {
    const schedule = context.scheduleStreamRender;
    if (!schedule) {
        throw new Error('Chat stream render schedule is not initialized');
    }
    return schedule;
}

export function cancelScheduledStreamRender(context: ChatStreamingControllerContext): void {
    context.scheduleStreamRender?.cancel();
}

export function dropPendingStreamRender(context: ChatStreamingControllerContext, message: ChatMessage, conversationId: string): void {
    context.scheduleStreamRender?.drop(message, conversationId);
}

const createConversationStreamState = (): ConversationStreamState => ({
    phase: 'idle',
    updatedAtMs: monotonicMs(),
    requestToken: 0,
    requestId: null,
    assistantTimestamp: null,
    currentConversationMountPending: false,
    currentConversationMountQueued: false,
    currentConversationMountPromise: null,
    comparisonRun: null,
    streamRenderSnapshot: null,
    terminalizationKey: null,
    terminalizationPromiseKey: null,
    terminalizationPromise: null,
    terminalizationResolve: null,
    terminalizationReject: null,
    terminalRenderToken: 0,
    terminalRenderTimerId: null,
    terminalRenderSettled: false,
    activityRefreshTimerId: null
});

export function requireConversationStreamState(context: ChatStreamingControllerContext, conversationId: string): ConversationStreamState {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        throw new Error('Chat stream state requires a valid conversationId');
    }
    const existing = context.streamStateByConversationId.get(normalizedConversationId);
    if (existing) {
        return existing;
    }
    const created = createConversationStreamState();
    context.streamStateByConversationId.set(normalizedConversationId, created);
    return created;
}

export function getConversationStreamState(context: ChatStreamingControllerContext, conversationId: string): ConversationStreamState | null {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return null;
    }
    return context.streamStateByConversationId.get(normalizedConversationId) ?? null;
}

export function invalidateMatchingStreamingElementCache(context: ChatStreamingControllerContext, conversationId: string, messageDomId: string): void {
    const normalizedConversationId = normalizeConversationId(conversationId);
    const cached = context.cachedStreamingElements;
    if (!normalizedConversationId || cached === null || cached.conversationId !== normalizedConversationId || cached.messageDomId !== messageDomId) {
        return;
    }
    context.cachedStreamingElements = null;
}

export function isConversationStreamingUiActive(context: ChatStreamingControllerContext, conversationId: string): boolean {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return false;
    }
    if (context.dependencies.chatStreamService.isStreaming(normalizedConversationId)) {
        return true;
    }
    const state = context.streamStateByConversationId.get(normalizedConversationId);
    if (!state || state.phase === 'idle') {
        return false;
    }
    return true;
}

export function isTerminalRenderPendingForMessage(context: ChatStreamingControllerContext, conversationId: string, message: ChatMessage): boolean {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId || message.role !== 'assistant') {
        return false;
    }
    const state = context.streamStateByConversationId.get(normalizedConversationId);
    if (!state || state.phase !== 'terminalizing' || state.terminalRenderSettled) {
        return false;
    }
    const assistantTimestamp = state.assistantTimestamp;
    if (!isFiniteNumber(assistantTimestamp)) {
        return false;
    }
    if (message.timestamp === assistantTimestamp) {
        return true;
    }
    return message.assistantTurnAtMs === assistantTimestamp;
}

export function setStreamPhase(context: ChatStreamingControllerContext, conversationId: string, phase: StreamLifecyclePhase): void {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        throw new Error('Chat stream phase requires a valid conversation id.');
    }
    const previousIsStreaming = isConversationStreamingUiActive(context, normalizedConversationId);
    setStreamPhaseState(context, normalizedConversationId, phase);
    applyStreamPhasePresentation(context, normalizedConversationId, previousIsStreaming);
}

export function setStreamPhaseState(context: ChatStreamingControllerContext, conversationId: string, phase: StreamLifecyclePhase): void {
    const state = requireConversationStreamState(context, conversationId);
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) throw new Error('Chat stream phase requires a valid conversation id.');
    state.phase = phase;
    state.updatedAtMs = monotonicMs();
    if (phase !== 'streaming') {
        clearActivityRefreshTimer(context, normalizedConversationId);
    }
    resolveConversationIdleWaiters(context.idleWaitersByConversationId, normalizedConversationId);
}

export function applyStreamPhasePresentation(context: ChatStreamingControllerContext, conversationId: string, previousIsStreaming: boolean): void {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) throw new Error('Chat stream phase presentation requires a valid conversation id.');
    const nextIsStreaming = isConversationStreamingUiActive(context, normalizedConversationId);
    applyStreamingUiTransition(context, {
        conversationId: normalizedConversationId,
        previousIsStreaming,
        nextIsStreaming,
        listRenderReason: 'Failed to render conversation list after stream phase change'
    });
}

export function syncStreamingControls(context: ChatStreamingControllerContext): void {
    syncCurrentConversationStreamingControls(context);
}

export function clearStreamingContext(context: ChatStreamingControllerContext, conversationId: string, options: { preserveComparisonRun?: boolean; resolveTerminalization?: boolean } = {}): void {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return;
    }
    const state = context.streamStateByConversationId.get(normalizedConversationId);
    if (!state) {
        return;
    }
    clearActivityRefreshTimer(context, normalizedConversationId);
    const previousIsStreaming = isConversationStreamingUiActive(context, normalizedConversationId);
    const preservedComparisonRun = options.preserveComparisonRun === true ? state.comparisonRun : null;
    if (state.terminalRenderTimerId !== null) {
        context.timers.clearTimeout(state.terminalRenderTimerId);
        state.terminalRenderTimerId = null;
    }
    if (options.resolveTerminalization !== false) {
        resolveConversationTerminalizationPromise(context, normalizedConversationId);
    }
    state.requestId = null;
    state.assistantTimestamp = null;
    state.currentConversationMountPending = false;
    state.currentConversationMountQueued = false;
    state.currentConversationMountPromise = null;
    state.comparisonRun = preservedComparisonRun;
    state.streamRenderSnapshot = null;
    state.terminalRenderSettled = false;
    state.phase = 'idle';
    state.updatedAtMs = monotonicMs();
    if (resolveCurrentConversationId(context) === normalizedConversationId) {
        cancelScheduledStreamRender(context);
        context.cachedStreamingElements = null;
    }
    const nextIsStreaming = isConversationStreamingUiActive(context, normalizedConversationId);
    resolveConversationIdleWaiters(context.idleWaitersByConversationId, normalizedConversationId);
    applyStreamingUiTransition(context, {
        conversationId: normalizedConversationId,
        previousIsStreaming,
        nextIsStreaming,
        listRenderReason: 'Failed to render conversation list after stream context clear'
    });
    if (preservedComparisonRun === null && options.resolveTerminalization !== false && state.activityRefreshTimerId === null && state.terminalRenderTimerId === null && !context.dependencies.chatStreamService.isStreaming(normalizedConversationId)) {
        context.streamStateByConversationId.delete(normalizedConversationId);
    }
}

export function reconcileInactiveSyncedConversation(context: ChatStreamingControllerContext, conversationId: string): void {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (context.disposed || !normalizedConversationId || context.dependencies.chatStreamService.isStreaming(normalizedConversationId)) {
        return;
    }
    const state = context.streamStateByConversationId.get(normalizedConversationId);
    if (state === undefined || state.terminalRenderTimerId !== null || state.terminalizationPromise !== null) {
        return;
    }
    if ((state.phase === 'stopping' || state.phase === 'stop_failed') && !context.dependencies.chatStreamService.canStartPromptNow(normalizedConversationId)) {
        return;
    }
    clearStreamingContext(context, normalizedConversationId);
}

export function disposeContext(context: ChatStreamingControllerContext): void {
    context.disposed = true;
    context.presentationActive = false;
    context.presentationGeneration += 1;

    context.serviceUnsubscribe?.();
    context.serviceUnsubscribe = null;
    const currentConversationId = resolveCurrentConversationId(context);
    if (currentConversationId) {
        clearActivityRefreshTimer(context, currentConversationId);
    }
    cancelScheduledStreamRender(context);
    context.reconcileActivityDurations = null;
    context.missingTargetRecoveryConversationId = null;
    context.scheduleStreamRender = null;
    context.timers.cleanup();
    resolveAllConversationTerminalizationPromises(context);
    rejectConversationIdleWaiters(context.idleWaitersByConversationId);
    context.streamStateByConversationId.clear();
    context.requestTokenByConversationId.clear();
    context.cachedStreamingElements = null;
}

export function suspendPresentationContext(context: ChatStreamingControllerContext): void {
    context.presentationActive = false;
    context.presentationGeneration += 1;
    cancelScheduledStreamRender(context);
    for (const conversationId of context.streamStateByConversationId.keys()) {
        clearActivityRefreshTimer(context, conversationId);
        resetConversationTerminalization(context, conversationId);
    }
    context.timers.cleanup();
    context.cachedStreamingElements = null;
}
