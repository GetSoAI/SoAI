/* SoAI - Chat feature service updates [frontend/assets/ts/features/chat/chatstreamservice/controller/serviceUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { awaitAnimationFrame } from '@core/runtime/animationFrames.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isObject } from '@core/typeGuards.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { upsertAssistantMessage } from '@features/chat/chatstreamservice/mappers.ts';
import { refreshActivityClock, shouldRefreshStreamActivityClock } from '@features/chat/chatstreamservice/controller/activityClock.ts';
import { clearStreamingContext, getConversationStreamState, isConversationStreamingUiActive, requireConversationStreamState, requireScheduleStreamRender, syncStreamingControls } from '@features/chat/chatstreamservice/controller/state.ts';
import { renderCurrentConversationSafely } from '@features/chat/chatstreamservice/controller/renderScheduling.ts';
import { resolveStableMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { resolveStreamRenderPatchType, resolveStreamRenderSnapshot, resolveStreamTextAppend } from '@features/chat/stream/streamRenderPatchType.ts';
import { resolveMountedStreamingAssistantRoot } from '@features/chat/stream/streamDomCache.ts';
import type { ChatStreamingControllerContext, ConversationStreamState, StreamUpdate } from '@features/chat/chatstreamservice/controller/types.ts';
import { scheduleRequestTerminalization } from '@features/chat/chatstreamservice/controller/terminalLifecycle.ts';
import { reportChatStreamTerminalizationFailureOnce } from '@features/chat/chatstreamservice/controller/terminalizationError.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import { isExpectedComparisonVariantUpdate, isFinalComparisonVariantTerminal, matchesActiveStreamUpdateIdentity, syncActiveComparisonRunFromUpdate } from '@features/chat/chatstreamservice/controller/comparisonRunUpdates.ts';
import { acceptStreamingServiceUpdateLifecycle, acceptTerminalServiceUpdateLifecycle, reconcileMismatchedTerminalServiceUpdate } from '@features/chat/chatstreamservice/controller/streamLifecycle.ts';

const hasMountedAssistantMessageRoot = (context: ChatStreamingControllerContext, conversationId: string, assistantMessage: ChatMessage): boolean => {
    const messagesArea = context.dependencies.presentation.optionalUI(CHAT_SELECTORS.MESSAGES);
    if (!messagesArea) {
        return false;
    }
    const messageDomId = resolveStableMessageDomId(assistantMessage);
    if (messageDomId === null) {
        throw new Error('Streaming assistant message requires a stable DOM id');
    }
    return resolveMountedStreamingAssistantRoot({ messagesArea, conversationId, messageDomId, cached: context.cachedStreamingElements }) !== null;
};

const runQueuedCurrentConversationMount = (context: ChatStreamingControllerContext, conversationId: string, state: ConversationStreamState): void => {
    state.currentConversationMountPending = true;
    const presentationGeneration = context.presentationGeneration;
    const requestId = state.requestId;
    const assistantTimestamp = state.assistantTimestamp;
    const mountCurrentConversation = async (): Promise<void> => {
        const currentState = getConversationStreamState(context, conversationId);
        if (context.disposed || !context.presentationActive || context.presentationGeneration !== presentationGeneration || currentState !== state || state.requestId !== requestId || state.assistantTimestamp !== assistantTimestamp || context.dependencies.state.getCurrentConversationId() !== conversationId) {
            return;
        }
        await renderCurrentConversationSafely(context, `Failed to mount current streaming assistant message for ${conversationId}`);
    };
    const mountPromise = mountCurrentConversation();
    state.currentConversationMountPromise = mountPromise;
    terminateHandledPromise(
        mountPromise.finally(() => {
            const currentState = getConversationStreamState(context, conversationId);
            if (currentState !== state) {
                return;
            }
            state.currentConversationMountPromise = null;
            if (state.requestId !== requestId || state.assistantTimestamp !== assistantTimestamp) {
                const shouldRunQueuedMount = state.currentConversationMountQueued && !context.disposed && context.dependencies.state.getCurrentConversationId() === conversationId;
                state.currentConversationMountPending = false;
                state.currentConversationMountQueued = false;
                if (shouldRunQueuedMount) {
                    runQueuedCurrentConversationMount(context, conversationId, state);
                }
                return;
            }
            state.currentConversationMountPending = false;
            if (!state.currentConversationMountQueued || context.disposed || !context.presentationActive || context.presentationGeneration !== presentationGeneration || context.dependencies.state.getCurrentConversationId() !== conversationId) {
                state.currentConversationMountQueued = false;
                return;
            }
            state.currentConversationMountQueued = false;
            runQueuedCurrentConversationMount(context, conversationId, state);
        })
    );
};

const ensureCurrentConversationStreamingMessageMounted = (context: ChatStreamingControllerContext, conversationId: string, assistantMessage: ChatMessage, state: ConversationStreamState): boolean => {
    if (context.dependencies.state.getCurrentConversationId() !== conversationId) {
        state.currentConversationMountPending = false;
        return false;
    }
    if (hasMountedAssistantMessageRoot(context, conversationId, assistantMessage)) {
        state.currentConversationMountPending = false;
        return false;
    }
    if (state.currentConversationMountPending) {
        state.currentConversationMountQueued = true;
        return true;
    }
    runQueuedCurrentConversationMount(context, conversationId, state);
    return true;
};

export const handleServiceUpdate = async (context: ChatStreamingControllerContext, update: StreamUpdate): Promise<void> => {
    if (!context.presentationActive) {
        return;
    }
    const presentationGeneration = context.presentationGeneration;
    const conversationId = normalizeConversationId(update.conversationId);
    if (!conversationId) {
        return;
    }
    const updateRequestId = update.requestId;
    const updateAssistantTimestamp = update.assistantTimestamp;
    const existingState = getConversationStreamState(context, conversationId);
    const hasActiveServiceStream = context.dependencies.chatStreamService.isStreaming(conversationId);
    const activeConversationId = normalizeConversationId(context.dependencies.state.getCurrentConversationId());
    const isCurrentConversationUpdate = activeConversationId === conversationId;
    if (!isCurrentConversationUpdate) {
        if (existingState !== null) {
            clearStreamingContext(context, conversationId, { preserveComparisonRun: existingState.comparisonRun !== null });
        }
        return;
    }
    const mutationType = update.mutation.type;
    const isPassiveTimelinePatch = update.status === 'streaming' && update.countsAsStreaming !== true && mutationType === 'timeline-event';
    if (update.status === 'streaming' && update.countsAsStreaming !== true && !isPassiveTimelinePatch) {
        if (existingState !== null) {
            clearStreamingContext(context, conversationId);
            return;
        }
        if (isCurrentConversationUpdate) {
            syncStreamingControls(context);
        }
        return;
    }
    if (update.status !== 'streaming' && existingState === null && !hasActiveServiceStream && !isCurrentConversationUpdate) {
        return;
    }
    const state = existingState ?? requireConversationStreamState(context, conversationId);
    const hadActiveStreamLifecycle = state.phase !== 'idle' || state.requestId !== null || state.assistantTimestamp !== null;
    const hasMismatchedActiveRequestId = Boolean(hadActiveStreamLifecycle && state.requestId !== null && updateRequestId !== state.requestId);
    const hasMismatchedActiveAssistantTimestamp = Boolean(hadActiveStreamLifecycle && state.assistantTimestamp !== null && updateAssistantTimestamp !== state.assistantTimestamp);
    const hasMismatchedActiveIdentity = hasMismatchedActiveRequestId || hasMismatchedActiveAssistantTimestamp;
    if (hasMismatchedActiveIdentity && !isExpectedComparisonVariantUpdate(state, update, updateRequestId)) {
        if (update.status !== 'streaming') {
            if (!matchesActiveStreamUpdateIdentity(state, update, updateRequestId)) {
                reconcileMismatchedTerminalServiceUpdate(context, {
                    conversationId,
                    state,
                    updateRequestId,
                    status: update.status
                });
                return;
            }
        } else if (hasActiveServiceStream || state.phase === 'starting') {
            return;
        }
    }
    if (isFinalComparisonVariantTerminal(state, update, updateRequestId)) {
        state.requestId = updateRequestId;
        state.assistantTimestamp = updateAssistantTimestamp;
    }
    if (update.status !== 'streaming' && !hadActiveStreamLifecycle && !hasActiveServiceStream && !isCurrentConversationUpdate) {
        clearStreamingContext(context, conversationId);
        return;
    }

    state.updatedAtMs = monotonicMs();
    const matchesActiveLifecycle = Boolean(hadActiveStreamLifecycle && state.requestId !== null && updateRequestId === state.requestId && (state.assistantTimestamp === null || updateAssistantTimestamp === state.assistantTimestamp));
    const treatAsPassiveStreamUpdate = update.status === 'streaming' && !hasActiveServiceStream && !isCurrentConversationUpdate && (!hadActiveStreamLifecycle || !matchesActiveLifecycle);

    if (update.status === 'streaming' && !treatAsPassiveStreamUpdate && !isPassiveTimelinePatch) {
        acceptStreamingServiceUpdateLifecycle(context, {
            conversationId,
            state,
            requestId: updateRequestId,
            assistantTimestamp: updateAssistantTimestamp
        });
    }
    if (!treatAsPassiveStreamUpdate && !isPassiveTimelinePatch) {
        syncStreamingControls(context);
    }

    let conversation = context.dependencies.conversations.get(conversationId);
    if (!conversation || !isObject(conversation)) {
        if (update.status !== 'streaming') {
            clearStreamingContext(context, conversationId);
        }
        return;
    }
    if (mutationType === 'initial-timeline') {
        try {
            await context.dependencies.storageManager.loadConversationMessages(conversationId, { force: true, mergeStreamingAssistants: true });
        } catch (error) {
            context.errorHandler?.error?.('ChatStream', `Canonical initial chat timeline synchronization failed for ${conversationId}`, ensureError(error));
        }
        if (context.disposed || !context.presentationActive || context.presentationGeneration !== presentationGeneration || getConversationStreamState(context, conversationId) !== state || state.requestId !== updateRequestId || state.assistantTimestamp !== updateAssistantTimestamp) {
            return;
        }
        const synchronizedConversation = context.dependencies.conversations.get(conversationId);
        if (synchronizedConversation && isObject(synchronizedConversation)) {
            conversation = synchronizedConversation;
        }
    }
    const assistantTimestamp = updateAssistantTimestamp;
    const assistantUpsert = upsertAssistantMessage(conversation, assistantTimestamp, update.message);
    if (!assistantUpsert.accepted) {
        return;
    }
    const assistantMessage = assistantUpsert.message;
    syncActiveComparisonRunFromUpdate(state, conversation, update, updateRequestId);
    if (update.status !== 'streaming') {
        acceptTerminalServiceUpdateLifecycle(context, {
            conversationId,
            state,
            requestId: updateRequestId,
            assistantTimestamp: updateAssistantTimestamp,
            shouldCaptureTerminalStreamIdentity: !hadActiveStreamLifecycle && hasActiveServiceStream,
            isUiActive: isConversationStreamingUiActive(context, conversationId)
        });
    }
    const previousSnapshot = state.streamRenderSnapshot;
    const nextSnapshot = resolveStreamRenderSnapshot(assistantMessage, update.assistantRevision, previousSnapshot);
    const patchType = resolveStreamRenderPatchType({
        status: update.status,
        message: assistantMessage,
        previous: previousSnapshot,
        next: nextSnapshot
    });
    const textAppend = resolveStreamTextAppend({
        status: update.status,
        mutationType,
        textDelta: update.mutation.textDelta,
        patchType,
        previous: previousSnapshot,
        next: nextSnapshot
    });
    state.streamRenderSnapshot = nextSnapshot;
    if (shouldRefreshStreamActivityClock(state, update.status, patchType)) {
        refreshActivityClock(context, assistantMessage, conversationId);
    }

    if (context.dependencies.state.getCurrentConversationId() === conversationId) {
        const isUiMounted = context.dependencies.presentation.optionalUI(CHAT_SELECTORS.MESSAGES) !== null;
        if (isUiMounted && patchType !== 'none') {
            const scheduleStreamRender = requireScheduleStreamRender(context);
            if (mutationType === 'initial-timeline') {
                await context.dependencies.presentation.renderCurrentConversation();
                if (context.disposed || !context.presentationActive || context.presentationGeneration !== presentationGeneration || context.dependencies.state.getCurrentConversationId() !== conversationId) {
                    return;
                }
                scheduleStreamRender({ message: assistantMessage, conversationId, patchType, assistantRevision: nextSnapshot.assistantRevision, textAppend });
                await awaitAnimationFrame(null, 'Chat initial timeline visual checkpoint aborted.');
                if (!context.presentationActive || context.presentationGeneration !== presentationGeneration) {
                    return;
                }
                await awaitAnimationFrame(null, 'Chat initial timeline visual checkpoint aborted.');
            } else if (isPassiveTimelinePatch) {
                if (hasMountedAssistantMessageRoot(context, conversationId, assistantMessage)) {
                    scheduleStreamRender({ message: assistantMessage, conversationId, patchType, assistantRevision: nextSnapshot.assistantRevision, textAppend });
                }
            } else {
                const mountPending = ensureCurrentConversationStreamingMessageMounted(context, conversationId, assistantMessage, state);
                if (!mountPending && update.status === 'streaming' && state.phase !== 'stopping') {
                    scheduleStreamRender({ message: assistantMessage, conversationId, patchType, assistantRevision: nextSnapshot.assistantRevision, textAppend });
                }
            }
        }
    }

    if (update.status !== 'streaming') {
        const resolvedRequestIdForTerminal = updateRequestId;
        const terminalLifecycleKnown = hadActiveStreamLifecycle || hasActiveServiceStream || isCurrentConversationUpdate;
        const shouldScheduleTerminal = terminalLifecycleKnown && (state.requestId === null || resolvedRequestIdForTerminal === state.requestId);
        if (shouldScheduleTerminal) {
            void scheduleRequestTerminalization(context, {
                conversationId,
                requestId: resolvedRequestIdForTerminal,
                assistantTimestamp,
                assistantMessage,
                status: update.status
            }).catch((error) => {
                const runtimeError = ensureError(error);
                reportChatStreamTerminalizationFailureOnce(runtimeError, (failure) => context.dependencies.reportRequestFailure(failure));
                context.errorHandler?.debug?.('ChatStream', `Terminalization scheduling failed for ${conversationId}`, runtimeError);
            });
        }
    }

    syncStreamingControls(context);
};
