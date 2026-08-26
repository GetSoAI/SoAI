/* SoAI - Chat stream controller cancellation coordination [frontend/assets/ts/features/chat/chatstreamservice/controller/actions/streamCancellation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { requestAgentTurnCancellation } from '@features/chat/chatstreamservice/controller/actions/agentTurnCancellation.ts';
import { cancelScheduledStreamRender, clearStreamingContext, getConversationStreamState, isConversationStreamingUiActive, setStreamPhase } from '@features/chat/chatstreamservice/controller/state.ts';
import { invalidateRequestToken } from '@features/chat/chatstreamservice/controller/actions/requestTracking.ts';
import { renderCurrentConversationSafely } from '@features/chat/chatstreamservice/controller/renderScheduling.ts';
import type { ChatStreamingControllerContext, ConversationStreamState } from '@features/chat/chatstreamservice/controller/types.ts';
import { markComparisonRunAborting } from '@features/chat/chatstreamservice/controller/streamLifecycle.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { scheduleRequestTerminalization } from '@features/chat/chatstreamservice/controller/terminalLifecycle.ts';
import type { ChatStreamStopOptions } from '@features/chat/chatstreamservice/types.ts';

const STOP_RECONCILIATION_WATCHDOG_MS = 12000;
const STOP_RECONCILIATION_RETRY_MS = 3000;
const STOP_RECONCILIATION_MAX_ATTEMPTS = 40;

const resolveStoppingAssistantMessage = (context: ChatStreamingControllerContext, conversationId: string, assistantTimestamp: number): ChatMessage | null => {
    const conversation = context.dependencies.conversations.get(conversationId);
    if (!conversation) {
        return null;
    }
    for (const message of conversation.messages) {
        if (isChatMessage(message) && message.role === 'assistant' && (message.timestamp === assistantTimestamp || message.assistantTurnAtMs === assistantTimestamp)) {
            return message;
        }
    }
    return null;
};

const resolveCurrentStreamCancellationConversationId = (context: ChatStreamingControllerContext): string | null => {
    const currentConversationId = context.dependencies.state.getCurrentConversationId();
    const normalizedCurrentConversationId = toTrimmedString(currentConversationId);
    return normalizedCurrentConversationId ? normalizedCurrentConversationId : null;
};

const normalizeStreamCancellationReason = (reason: string | undefined): string | null => {
    if (!isString(reason)) {
        return null;
    }
    const normalized = reason.trim();
    return normalized ? normalized : null;
};

const requestActiveAgentTurnCancellation = (context: ChatStreamingControllerContext, conversationId: string, forcePendingSteers: boolean): void => {
    try {
        requestAgentTurnCancellation(context, conversationId, forcePendingSteers);
    } catch (error) {
        const runtimeError = ensureError(error);
        context.errorHandler?.debug?.('ChatStream', 'Failed to request active agent turn cancellation', runtimeError);
    }
};

const renderCurrentConversationAfterLocalCancellation = (context: ChatStreamingControllerContext, conversationId: string): void => {
    const currentConversationId = toTrimmedString(context.dependencies.state.getCurrentConversationId());
    if (context.disposed || !context.presentationActive || currentConversationId !== conversationId) {
        return;
    }
    context.dependencies.presentation.invalidateChatMarkup('current');
    terminateHandledPromise(renderCurrentConversationSafely(context, `Failed to render current conversation after pending stream cancellation for ${conversationId}`));
};

const scheduleStopReconciliationWatchdog = (context: ChatStreamingControllerContext, conversationId: string, requestId: string | null, attempt = 0): void => {
    context.timers.setTimeout(
        () => {
            const state = getConversationStreamState(context, conversationId);
            if (context.disposed || state === null || state.phase !== 'stopping' || (requestId !== null && state.requestId !== requestId)) {
                return;
            }
            void context.dependencies.chatStreamService
                .syncConversationStatus(conversationId)
                .then(async () => {
                    const currentState = getConversationStreamState(context, conversationId);
                    if (context.disposed || currentState === null || currentState.phase !== 'stopping' || (requestId !== null && currentState.requestId !== requestId)) {
                        return;
                    }
                    if (context.dependencies.chatStreamService.isStreaming(conversationId)) {
                        const activeRequestId = context.dependencies.chatStreamService.getStreamIdentity(conversationId)?.requestId ?? null;
                        if (requestId !== null && activeRequestId !== null && activeRequestId !== requestId) {
                            return;
                        }
                        const nextAttempt = attempt + 1;
                        if (nextAttempt >= STOP_RECONCILIATION_MAX_ATTEMPTS) {
                            context.errorHandler?.debug?.('ChatStream', `Stopped stream remained active after reconciliation for ${conversationId}`);
                            return;
                        }
                        scheduleStopReconciliationWatchdog(context, conversationId, requestId, nextAttempt);
                        return;
                    }
                    const settledState = getConversationStreamState(context, conversationId);
                    if (context.disposed || settledState === null || settledState.phase !== 'stopping' || (requestId !== null && settledState.requestId !== requestId)) {
                        return;
                    }
                    const assistantTimestamp = settledState.assistantTimestamp;
                    if (!isFiniteNumber(assistantTimestamp)) {
                        context.errorHandler?.debug?.('ChatStream', `Stopped stream is missing its assistant identity for ${conversationId}`);
                        return;
                    }
                    await scheduleRequestTerminalization(context, {
                        conversationId,
                        requestId: settledState.requestId,
                        assistantTimestamp,
                        assistantMessage: resolveStoppingAssistantMessage(context, conversationId, assistantTimestamp),
                        status: 'cancelled'
                    });
                })
                .catch((error) => {
                    const runtimeError = ensureError(error);
                    context.errorHandler?.debug?.('ChatStream', `Failed to reconcile stopped stream for ${conversationId}`, runtimeError);
                });
        },
        attempt === 0 ? STOP_RECONCILIATION_WATCHDOG_MS : STOP_RECONCILIATION_RETRY_MS
    );
};

const resolveActiveCancellationIdentity = (context: ChatStreamingControllerContext, conversationId: string): { requestId: string | null; assistantTimestamp: number | null } => {
    const streamState = getConversationStreamState(context, conversationId);
    if (streamState?.requestId) {
        return { requestId: streamState.requestId, assistantTimestamp: streamState.assistantTimestamp };
    }
    const serviceIdentity = context.dependencies.chatStreamService.getStreamIdentity(conversationId);
    return {
        requestId: serviceIdentity?.requestId ?? null,
        assistantTimestamp: serviceIdentity?.assistantTimestamp ?? null
    };
};

const requestStreamStop = (context: ChatStreamingControllerContext, conversationId: string, requestId: string | null, options: ChatStreamStopOptions): void => {
    const normalizedReason = normalizeStreamCancellationReason(options.reason);
    context.dependencies.chatStreamService.stop({
        conversationId,
        force: true,
        ...(options.forcePendingSteers === undefined ? {} : { forcePendingSteers: options.forcePendingSteers }),
        ...(requestId === null ? {} : { requestId }),
        ...(normalizedReason === null ? {} : { reason: normalizedReason })
    });
};

const cancelPendingStartingStreamForConversation = (context: ChatStreamingControllerContext, conversationId: string, streamState: ConversationStreamState, options: ChatStreamStopOptions): void => {
    invalidateRequestToken(context, conversationId);
    cancelScheduledStreamRender(context);
    context.cachedStreamingElements = null;
    requestActiveAgentTurnCancellation(context, conversationId, options.forcePendingSteers === true);
    markComparisonRunAborting(streamState);
    const requestId = streamState.requestId;
    requestStreamStop(context, conversationId, requestId, options);
    clearStreamingContext(context, conversationId);
    renderCurrentConversationAfterLocalCancellation(context, conversationId);
};

const cancelActiveStreamForConversation = (context: ChatStreamingControllerContext, conversationId: string, options: ChatStreamStopOptions = {}): void => {
    const streamState = getConversationStreamState(context, conversationId);
    const streamLifecycle = context.dependencies.chatStreamService.getStreamLifecycle(conversationId);
    if (!isConversationStreamingUiActive(context, conversationId) && streamLifecycle === 'inactive') {
        clearStreamingContext(context, conversationId);
        return;
    }
    if (streamState?.phase === 'stopping') {
        return;
    }
    if (streamState?.phase === 'terminalizing') {
        return;
    }
    if (streamState?.phase === 'starting' && !context.dependencies.chatStreamService.isStreaming(conversationId)) {
        if (options.expectedRequestId && streamState.requestId !== options.expectedRequestId) {
            return;
        }
        cancelPendingStartingStreamForConversation(context, conversationId, streamState, options);
        return;
    }

    const cancellationIdentity = resolveActiveCancellationIdentity(context, conversationId);
    if (options.expectedRequestId && cancellationIdentity.requestId !== options.expectedRequestId) {
        return;
    }

    cancelScheduledStreamRender(context);
    context.cachedStreamingElements = null;
    requestActiveAgentTurnCancellation(context, conversationId, options.forcePendingSteers === true);
    if (streamState) {
        markComparisonRunAborting(streamState);
    }
    const requestId = cancellationIdentity.requestId;
    setStreamPhase(context, conversationId, 'stopping');
    const stoppingState = getConversationStreamState(context, conversationId);
    if (stoppingState !== null && stoppingState.requestId === null) {
        stoppingState.requestId = requestId;
    }
    if (stoppingState !== null && stoppingState.assistantTimestamp === null) {
        stoppingState.assistantTimestamp = cancellationIdentity.assistantTimestamp;
    }
    requestStreamStop(context, conversationId, requestId, options);
    scheduleStopReconciliationWatchdog(context, conversationId, requestId);
};

const interruptActiveStreamForConversation = (context: ChatStreamingControllerContext, conversationId: string, reason?: string): void => {
    const streamState = getConversationStreamState(context, conversationId);
    const requestId = streamState?.requestId ?? null;
    invalidateRequestToken(context, conversationId);
    cancelScheduledStreamRender(context);
    context.cachedStreamingElements = null;
    requestActiveAgentTurnCancellation(context, conversationId, false);
    if (streamState) {
        markComparisonRunAborting(streamState);
    }
    const interruptedSnapshot = context.dependencies.chatStreamService.interrupt({
        conversationId,
        requestId,
        ...(reason === undefined ? {} : { reason })
    });
    if (!interruptedSnapshot) {
        clearStreamingContext(context, conversationId);
    }
};

export { cancelActiveStreamForConversation, interruptActiveStreamForConversation, resolveCurrentStreamCancellationConversationId };
