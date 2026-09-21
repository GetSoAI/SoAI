/* SoAI - Chat stream controller lifecycle transitions [frontend/assets/ts/features/chat/chatstreamservice/controller/streamLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isActiveRequest } from '@features/chat/chatstreamservice/controller/actions/requestTracking.ts';
import { resolveComparisonGroupRequestId } from '@features/chat/chatstreamservice/comparisonRequestIdentity.ts';
import { renderCurrentConversationSafely } from '@features/chat/chatstreamservice/controller/renderScheduling.ts';
import { clearStreamingContext, getConversationStreamState, setStreamPhase, syncStreamingControls } from '@features/chat/chatstreamservice/controller/state.ts';
import { resetConversationTerminalization, waitForTerminalReconciliation } from '@features/chat/chatstreamservice/controller/terminalizationState.ts';
import type { ChatStreamingControllerContext, ConversationStreamState } from '@features/chat/chatstreamservice/controller/types.ts';
import type { ChatStreamMessageSavedReconciliation } from '@features/chat/chatstreamservice/messageSavedReconciliation.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import { resolveConversationIdleWaiters } from '@features/chat/chatstreamservice/controller/idleWaiters.ts';

const beginStreamStartLifecycle = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; groupRequestId: string; state: ConversationStreamState }): void => {
    inputArguments.state.requestId = inputArguments.groupRequestId;
    inputArguments.state.assistantTimestamp = null;
    inputArguments.state.streamRenderSnapshot = null;
    context.cachedStreamingElements = null;
    resetConversationTerminalization(context, inputArguments.conversationId);
    setStreamPhase(context, inputArguments.conversationId, 'starting');
};

const abortPendingStreamStartLifecycle = (context: ChatStreamingControllerContext, conversationId: string, note: string): void => {
    context.errorHandler?.debug?.('ChatStream', `Aborting pending stream start: ${note}`);
    clearStreamingContext(context, conversationId);
};

const beginComparisonVariantLifecycle = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; state: ConversationStreamState; requestId: string; assistantTimestamp: number }): void => {
    setStreamPhase(context, inputArguments.conversationId, 'starting');
    inputArguments.state.requestId = inputArguments.requestId;
    inputArguments.state.assistantTimestamp = inputArguments.assistantTimestamp;
    inputArguments.state.streamRenderSnapshot = null;
};

const markComparisonRunAborting = (state: ConversationStreamState): void => {
    if (state.comparisonRun) {
        state.comparisonRun.aborting = true;
    }
};

const acceptStreamingServiceUpdateLifecycle = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; state: ConversationStreamState; requestId: string | null; assistantTimestamp: number | null }): void => {
    if (inputArguments.state.phase === 'stopping' || inputArguments.state.phase === 'stop_failed') {
        syncStreamingControls(context);
        return;
    }
    const streamIdentityChanged = inputArguments.state.requestId !== inputArguments.requestId || inputArguments.state.assistantTimestamp !== inputArguments.assistantTimestamp;
    resetConversationTerminalization(context, inputArguments.conversationId);
    inputArguments.state.requestId = inputArguments.requestId;
    inputArguments.state.assistantTimestamp = inputArguments.assistantTimestamp;
    if (streamIdentityChanged) {
        inputArguments.state.streamRenderSnapshot = null;
    }
    setStreamPhase(context, inputArguments.conversationId, 'streaming');
    resolveConversationIdleWaiters(context.idleWaitersByConversationId, inputArguments.conversationId);
};

const acceptTerminalServiceUpdateLifecycle = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; state: ConversationStreamState; requestId: string | null; assistantTimestamp: number | null; shouldCaptureTerminalStreamIdentity: boolean; isUiActive: boolean }): void => {
    if (inputArguments.state.phase === 'idle' && inputArguments.shouldCaptureTerminalStreamIdentity) {
        inputArguments.state.requestId = inputArguments.requestId;
        inputArguments.state.assistantTimestamp = inputArguments.assistantTimestamp;
    }
    const shouldSettleExecution = inputArguments.isUiActive && (inputArguments.requestId === null || inputArguments.state.requestId === null || inputArguments.requestId === inputArguments.state.requestId);
    if (shouldSettleExecution) {
        setStreamPhase(context, inputArguments.conversationId, 'terminalizing');
    }
};

const reconcileMismatchedTerminalServiceUpdate = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; state: ConversationStreamState; updateRequestId: string | null }): void => {
    if (context.dependencies.chatStreamService.isStreaming(inputArguments.conversationId)) {
        return;
    }
    const updateGroupRequestId = inputArguments.updateRequestId === null ? null : resolveComparisonGroupRequestId(inputArguments.updateRequestId);
    if (inputArguments.state.phase === 'starting' && updateGroupRequestId !== inputArguments.state.requestId) {
        context.errorHandler?.debug?.('ChatStream', `Ignoring foreign terminal update during pending stream start for ${inputArguments.conversationId}`);
        return;
    }
    if (!context.disposed && context.presentationActive && context.dependencies.state.getCurrentConversationId() === inputArguments.conversationId) {
        context.dependencies.presentation.invalidateChatMarkup('current');
        terminateHandledPromise(renderCurrentConversationSafely(context, `Failed to reconcile historical terminal messages for ${inputArguments.conversationId}`));
    }
};

const isBackendStreamActive = (context: ChatStreamingControllerContext, conversationId: string, reconciliation: ChatStreamMessageSavedReconciliation | null): boolean => {
    if (context.dependencies.chatStreamService.isStreaming(conversationId)) {
        return true;
    }
    if (context.dependencies.chatStreamService.getStreamLifecycle(conversationId) !== 'inactive') {
        return true;
    }
    return reconciliation?.startAdmission === 'busy';
};

const startOutcomeStillMatchesState = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; requestToken: number; requestId: string; assistantTimestamp: number }): boolean => {
    if (!isActiveRequest(context, inputArguments.conversationId, inputArguments.requestToken)) {
        return false;
    }
    const state = getConversationStreamState(context, inputArguments.conversationId);
    if (state === null || state.phase === 'idle') {
        return false;
    }
    return state.requestId === inputArguments.requestId && state.assistantTimestamp === inputArguments.assistantTimestamp;
};

const renderCurrentConversationAfterStartSettlement = async (context: ChatStreamingControllerContext, conversationId: string): Promise<void> => {
    if (context.disposed || !context.presentationActive || normalizeConversationId(context.dependencies.state.getCurrentConversationId()) !== conversationId) {
        return;
    }
    context.dependencies.presentation.invalidateChatMarkup('current');
    await renderCurrentConversationSafely(context, `Failed to render current conversation after non-complete stream start settlement for ${conversationId}`);
};

const settleNonCompleteStreamStartOutcome = async (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; requestToken: number; requestId: string; assistantTimestamp: number; signal?: AbortSignal | null }): Promise<void> => {
    await waitForTerminalReconciliation(context, inputArguments.conversationId, inputArguments.signal ?? null);
    if (!startOutcomeStillMatchesState(context, inputArguments)) {
        return;
    }
    let reconciliation: ChatStreamMessageSavedReconciliation | null = null;
    try {
        reconciliation = await context.dependencies.chatStreamService.syncConversationStatus(inputArguments.conversationId);
    } catch (error) {
        context.errorHandler?.debug?.('ChatStream', `Failed to sync stream status after non-complete start for ${inputArguments.conversationId}`, ensureError(error));
    }
    if (!startOutcomeStillMatchesState(context, inputArguments)) {
        return;
    }
    await waitForTerminalReconciliation(context, inputArguments.conversationId, inputArguments.signal ?? null);
    if (!startOutcomeStillMatchesState(context, inputArguments) || isBackendStreamActive(context, inputArguments.conversationId, reconciliation)) {
        return;
    }
    try {
        await context.dependencies.storageManager.loadConversationMessages(inputArguments.conversationId, { force: true });
    } catch (error) {
        context.errorHandler?.debug?.('ChatStream', `Failed to reload messages after non-complete start for ${inputArguments.conversationId}`, ensureError(error));
    }
    if (!startOutcomeStillMatchesState(context, inputArguments)) {
        return;
    }
    await waitForTerminalReconciliation(context, inputArguments.conversationId, inputArguments.signal ?? null);
    if (!startOutcomeStillMatchesState(context, inputArguments) || isBackendStreamActive(context, inputArguments.conversationId, reconciliation)) {
        return;
    }
    clearStreamingContext(context, inputArguments.conversationId);
    await renderCurrentConversationAfterStartSettlement(context, inputArguments.conversationId);
};

export { abortPendingStreamStartLifecycle, acceptStreamingServiceUpdateLifecycle, acceptTerminalServiceUpdateLifecycle, beginComparisonVariantLifecycle, beginStreamStartLifecycle, markComparisonRunAborting, reconcileMismatchedTerminalServiceUpdate, settleNonCompleteStreamStartOutcome };
