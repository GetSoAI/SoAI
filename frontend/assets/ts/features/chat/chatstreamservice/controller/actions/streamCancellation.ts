/* SoAI - Chat stream controller cancellation coordination [frontend/assets/ts/features/chat/chatstreamservice/controller/actions/streamCancellation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';
import { applyStreamPhasePresentation, cancelScheduledStreamRender, clearStreamingContext, getConversationStreamState, isConversationStreamingUiActive, requireConversationStreamState, setStreamPhase, setStreamPhaseState } from '@features/chat/chatstreamservice/controller/state.ts';
import { invalidateRequestToken } from '@features/chat/chatstreamservice/controller/actions/requestTracking.ts';
import type { ChatStreamingControllerContext } from '@features/chat/chatstreamservice/controller/types.ts';
import { markComparisonRunAborting } from '@features/chat/chatstreamservice/controller/streamLifecycle.ts';
import type { ChatStreamStopOptions } from '@features/chat/chatstreamservice/types.ts';

const resolveCurrentStreamCancellationConversationId = (context: ChatStreamingControllerContext): string | null => {
    const conversationId = toTrimmedString(context.dependencies.state.getCurrentConversationId());
    return conversationId || null;
};

const normalizeStreamCancellationReason = (reason: string | undefined): string | null => {
    if (!isString(reason)) return null;
    const normalized = reason.trim();
    return normalized || null;
};

const resolveCancellationRequestId = (context: ChatStreamingControllerContext, conversationId: string): string | null => {
    return getConversationStreamState(context, conversationId)?.requestId ?? context.dependencies.chatStreamService.getStreamIdentity(conversationId)?.requestId ?? null;
};

const stopProjectionIsCurrent = (context: ChatStreamingControllerContext, conversationId: string, requestId: string, executionGeneration: number | null): boolean => {
    const currentGeneration = context.requestTokenByConversationId.get(conversationId) ?? null;
    const state = getConversationStreamState(context, conversationId);
    return currentGeneration === executionGeneration && state !== null && state.requestId === requestId;
};

const projectRetryableStop = (context: ChatStreamingControllerContext, conversationId: string, requestId: string, executionGeneration: number | null): void => {
    const state = getConversationStreamState(context, conversationId);
    if (!stopProjectionIsCurrent(context, conversationId, requestId, executionGeneration) || state?.phase !== 'stopping') return;
    setStreamPhase(context, conversationId, 'stop_failed');
    context.dependencies.reportRequestFailure(new Error(i18n.t('common.cancellation.failed')));
};

const observeStopOutcome = (context: ChatStreamingControllerContext, conversationId: string, requestId: string, executionGeneration: number | null, stopPromise: Promise<'terminal' | 'failed' | 'unconfirmed'>): void => {
    terminateHandledPromise(
        stopPromise.then(async (outcome) => {
            if (!stopProjectionIsCurrent(context, conversationId, requestId, executionGeneration)) return;
            if (outcome === 'terminal') {
                await context.dependencies.chatStreamService.syncConversationStatus(conversationId);
                return;
            }
            projectRetryableStop(context, conversationId, requestId, executionGeneration);
        })
    );
};

const projectTerminalStopEvidence = (context: ChatStreamingControllerContext, conversationId: string, requestId: string, executionGeneration: number | null): void => {
    if (!stopProjectionIsCurrent(context, conversationId, requestId, executionGeneration)) return;
    if (context.dependencies.chatStreamService.getStreamLifecycle(conversationId) === 'inactive') {
        clearStreamingContext(context, conversationId);
        return;
    }
    setStreamPhase(context, conversationId, 'terminalizing');
};

const cancelActiveStreamForConversation = (context: ChatStreamingControllerContext, conversationId: string, options: ChatStreamStopOptions = {}): void => {
    const streamState = getConversationStreamState(context, conversationId);
    const lifecycle = context.dependencies.chatStreamService.getStreamLifecycle(conversationId);
    if (!isConversationStreamingUiActive(context, conversationId) && lifecycle === 'inactive') {
        if (streamState !== null) clearStreamingContext(context, conversationId);
        return;
    }
    if (streamState?.phase === 'stopping' || streamState?.phase === 'terminalizing') return;
    const requestId = resolveCancellationRequestId(context, conversationId);
    if (requestId === null || (options.expectedRequestId !== undefined && options.expectedRequestId !== requestId)) return;
    const executionGeneration = context.requestTokenByConversationId.get(conversationId) ?? null;
    const previousIsStreaming = isConversationStreamingUiActive(context, conversationId);
    const stoppingState = streamState ?? requireConversationStreamState(context, conversationId);
    stoppingState.requestId = requestId;
    setStreamPhaseState(context, conversationId, 'stopping');
    const reason = normalizeStreamCancellationReason(options.reason);
    const stopPromise = context.dependencies.chatStreamService.stop({
        conversationId,
        requestId,
        force: true,
        forcePendingSteers: options.forcePendingSteers === true,
        onTerminalEvidence: () => projectTerminalStopEvidence(context, conversationId, requestId, executionGeneration),
        ...(reason === null ? {} : { reason })
    });
    markComparisonRunAborting(stoppingState);
    applyStreamPhasePresentation(context, conversationId, previousIsStreaming);
    cancelScheduledStreamRender(context);
    context.cachedStreamingElements = null;
    if (stopPromise === null) {
        projectRetryableStop(context, conversationId, requestId, executionGeneration);
        return;
    }
    observeStopOutcome(context, conversationId, requestId, executionGeneration, stopPromise);
};

const interruptActiveStreamForConversation = (context: ChatStreamingControllerContext, conversationId: string, reason?: string): void => {
    const streamState = getConversationStreamState(context, conversationId);
    invalidateRequestToken(context, conversationId);
    cancelScheduledStreamRender(context);
    context.cachedStreamingElements = null;
    if (streamState) markComparisonRunAborting(streamState);
    context.dependencies.chatStreamService.interrupt({
        conversationId,
        requestId: streamState?.requestId ?? null,
        ...(reason === undefined ? {} : { reason })
    });
};

export { cancelActiveStreamForConversation, interruptActiveStreamForConversation, resolveCurrentStreamCancellationConversationId };
