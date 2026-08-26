/* SoAI - Chat feature terminal lifecycle [frontend/assets/ts/features/chat/chatstreamservice/controller/terminalLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createDeferred, type DeferredRejectionReason } from '@core/runtime/deferred.ts';
import { TIMEOUTS } from '@core/constants.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { reconcileCanonicalTerminalMessages } from '@features/chat/chatstreamservice/controller/canonicalTerminalHydration.ts';
import { isChatTurnSuperseded } from '@features/chat/chatstreamservice/controller/turnSupersession.ts';
import { clearStreamingContext, dropPendingStreamRender, getConversationStreamState, requireConversationStreamState, setStreamPhase } from '@features/chat/chatstreamservice/controller/state.ts';
import type { ChatStreamingControllerContext } from '@features/chat/chatstreamservice/controller/types.ts';
import { renderCurrentConversationSafely, scheduleConversationListRender } from '@features/chat/chatstreamservice/controller/renderScheduling.ts';
import { isTerminalAssistantSettlementReceiptCurrent, resolveTerminalAssistantSettlementFingerprint, settleTerminalAssistantMessageDom, type TerminalAssistantSettlementReceipt } from '@features/chat/chatstreamservice/controller/terminalAssistantSettlement.ts';
import { ChatStreamTerminalizationError } from '@features/chat/chatstreamservice/controller/terminalizationError.ts';
import { buildTerminalizationKey, hasTerminalStateMismatch, isTerminalizationWaiterCurrent, prepareCurrentConversationForTerminalization, settleTerminalizationWaiter, shouldKeepStreamingUiActiveAfterTerminal } from '@features/chat/chatstreamservice/controller/terminalizationFlow.ts';
import { resetConversationTerminalization } from '@features/chat/chatstreamservice/controller/terminalizationState.ts';

const hasCanonicalMessagesAfterTerminalizedTurn = (context: ChatStreamingControllerContext, conversationId: string, assistantTimestamp: number): boolean => {
    const conversation = context.dependencies.conversations.get(conversationId);
    if (!conversation) {
        return false;
    }
    return conversation.messages.some((message) => isFiniteNumber(message.timestamp) && message.timestamp > assistantTimestamp);
};

export const scheduleRequestTerminalization = async (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; requestId: string | null; assistantTimestamp: number; assistantMessage?: ChatMessage | null; status: 'complete' | 'error' | 'cancelled' }): Promise<void> => {
    const assistantMessage = inputArguments.assistantMessage ?? null;
    const state = requireConversationStreamState(context, inputArguments.conversationId);
    if (hasTerminalStateMismatch(state, inputArguments)) {
        if (context.dependencies.chatStreamService.isStreaming(inputArguments.conversationId)) {
            context.errorHandler?.debug?.('ChatStream', `Skipping mismatched terminalization while the service stream is active for ${inputArguments.conversationId}`);
            return;
        }
        const stateAssistantTimestamp = state.assistantTimestamp;
        if (typeof stateAssistantTimestamp === 'number' && Number.isFinite(stateAssistantTimestamp)) {
            await scheduleRequestTerminalization(context, {
                conversationId: inputArguments.conversationId,
                requestId: state.requestId,
                assistantTimestamp: stateAssistantTimestamp,
                status: inputArguments.status
            });
            return;
        }
        clearStreamingContext(context, inputArguments.conversationId);
        if (!context.disposed && context.presentationActive && context.dependencies.state.getCurrentConversationId() === inputArguments.conversationId) {
            context.dependencies.presentation.invalidateChatMarkup('current');
            await renderCurrentConversationSafely(context, `Failed to render current conversation after mismatched terminal cleanup for ${inputArguments.conversationId}`);
        }
        return;
    }
    prepareCurrentConversationForTerminalization(context, {
        conversationId: inputArguments.conversationId,
        assistantMessage
    });

    const terminalizationKey = buildTerminalizationKey({
        requestId: inputArguments.requestId,
        assistantTimestamp: inputArguments.assistantTimestamp
    });
    if (state.terminalizationKey === terminalizationKey && state.terminalizationPromise !== null) {
        await state.terminalizationPromise;
        return;
    }
    if (state.terminalizationKey === terminalizationKey && state.terminalRenderTimerId !== null) {
        throw new Error('Chat stream terminalization timer is pending without a completion promise.');
    }
    resetConversationTerminalization(context, inputArguments.conversationId);
    state.terminalizationKey = terminalizationKey;
    const doneDeferred = createDeferred<void>();
    const donePromise = doneDeferred.promise;
    state.terminalizationPromiseKey = terminalizationKey;
    state.terminalizationPromise = donePromise;
    const resolveDone = (): void => {
        doneDeferred.resolve();
    };
    const rejectDone = (error: DeferredRejectionReason): void => {
        doneDeferred.reject(error);
    };
    state.terminalizationResolve = resolveDone;
    state.terminalizationReject = rejectDone;

    state.terminalRenderToken += 1;
    const token = state.terminalRenderToken;
    state.terminalRenderTimerId = context.timers.setTimeout((): void => {
        const settleDone = (): void => {
            settleTerminalizationWaiter(context, { conversationId: inputArguments.conversationId, terminalizationKey, resolve: resolveDone, reject: rejectDone });
        };
        const settleFailed = (error: DeferredRejectionReason): void => {
            const runtimeError = ensureError(error);
            context.errorHandler?.debug?.('ChatStream', `Terminalization failed for ${inputArguments.conversationId}`, runtimeError);
            settleTerminalizationWaiter(context, { conversationId: inputArguments.conversationId, terminalizationKey, resolve: resolveDone, reject: rejectDone, error: new ChatStreamTerminalizationError(inputArguments.conversationId, runtimeError) });
        };
        const currentState = getConversationStreamState(context, inputArguments.conversationId);
        if (context.disposed || currentState === null || currentState.terminalRenderToken !== token) {
            settleDone();
            return;
        }
        currentState.terminalRenderTimerId = null;

        const isCurrentTerminalization = (): boolean =>
            isTerminalizationWaiterCurrent(context, {
                conversationId: inputArguments.conversationId,
                terminalizationKey,
                resolve: resolveDone,
                reject: rejectDone
            });
        const hasSupersedingStream = (): boolean =>
            isChatTurnSuperseded(context.dependencies.chatStreamService, {
                conversationId: inputArguments.conversationId,
                assistantTimestamp: inputArguments.assistantTimestamp
            });
        const recoverTerminalizationFailure = (error: DeferredRejectionReason): Error => {
            const runtimeError = ensureError(error);
            if (!context.dependencies.chatStreamService.isStreaming(inputArguments.conversationId) || hasSupersedingStream()) {
                clearStreamingContext(context, inputArguments.conversationId, { resolveTerminalization: false });
            }
            if (!context.disposed && context.presentationActive && context.dependencies.state.getCurrentConversationId() === inputArguments.conversationId) {
                context.dependencies.presentation.invalidateChatMarkup('current');
                terminateHandledPromise(renderCurrentConversationSafely(context, `Failed to render current conversation after terminal sync failure for ${inputArguments.conversationId}`));
                scheduleConversationListRender(context, 'Failed to render conversation list after terminal sync failure');
            }
            return runtimeError;
        };
        const runAfterCanonicalSync = (operation: () => Promise<void> | void): void => {
            const run = async (): Promise<void> => {
                if (context.disposed || !isCurrentTerminalization()) {
                    return;
                }
                const canonicalMessagesLoaded = await reconcileCanonicalTerminalMessages(context, {
                    conversationId: inputArguments.conversationId,
                    assistantMessage,
                    assistantTimestamp: inputArguments.assistantTimestamp,
                    requireToolSettlement: inputArguments.status !== 'complete' || currentState.phase === 'stopping',
                    isCurrentTerminalization
                });
                if (!canonicalMessagesLoaded || context.disposed || !isCurrentTerminalization()) {
                    return;
                }
                await operation();
            };
            const reconciliation = withTimeout(run(), {
                timeoutMs: TIMEOUTS.PAGE_LOAD,
                timeoutMessage: `Chat stream terminal reconciliation timed out for ${inputArguments.conversationId}`
            }).catch((error) => {
                throw recoverTerminalizationFailure(error);
            });
            terminateHandledPromise(reconciliation.then(settleDone, settleFailed));
        };
        const clearAfterRecovery = (optimisticSignature: string | null, optimisticReceipt: TerminalAssistantSettlementReceipt | null): void => {
            runAfterCanonicalSync(async () => {
                const activeConversationId = context.dependencies.state.getCurrentConversationId();
                let terminalDomSettled = false;
                let conversationListRenderAlreadyScheduled = false;
                if (context.presentationActive && activeConversationId === inputArguments.conversationId && assistantMessage !== null) {
                    dropPendingStreamRender(context, assistantMessage, inputArguments.conversationId);
                    context.cachedStreamingElements = null;
                    const settlementArguments = {
                        conversationId: inputArguments.conversationId,
                        assistantMessage,
                        activeConversationId
                    };
                    const canonicalSignature = resolveTerminalAssistantSettlementFingerprint(context, settlementArguments);
                    terminalDomSettled = optimisticSignature !== null && canonicalSignature === optimisticSignature && optimisticReceipt !== null && isTerminalAssistantSettlementReceiptCurrent(context, optimisticReceipt);
                    if (!terminalDomSettled) {
                        terminalDomSettled = settleTerminalAssistantMessageDom(context, { ...settlementArguments, canonicalCorrection: optimisticSignature !== null }) !== null;
                    }
                }
                clearStreamingContext(context, inputArguments.conversationId, { resolveTerminalization: false });
                const hasSucceedingCanonicalMessages = hasCanonicalMessagesAfterTerminalizedTurn(context, inputArguments.conversationId, inputArguments.assistantTimestamp);
                if (!context.disposed && context.presentationActive && activeConversationId === inputArguments.conversationId && (!terminalDomSettled || hasSucceedingCanonicalMessages)) {
                    context.dependencies.presentation.invalidateChatMarkup('current');
                    await renderCurrentConversationSafely(context, `Failed to reconcile current conversation after stream completion for ${inputArguments.conversationId}`);
                    scheduleConversationListRender(context, 'Failed to render conversation list after current stream terminal reconciliation');
                    conversationListRenderAlreadyScheduled = true;
                }
                if (!context.disposed) {
                    const onStreamTerminalUpdate = context.dependencies.onStreamTerminalUpdate;
                    if (onStreamTerminalUpdate) {
                        onStreamTerminalUpdate({
                            conversationId: inputArguments.conversationId,
                            requestId: inputArguments.requestId,
                            assistantTimestamp: inputArguments.assistantTimestamp,
                            status: inputArguments.status,
                            conversationListRenderAlreadyScheduled
                        });
                    }
                }
                if (!context.disposed && hasSupersedingStream()) {
                    context.dependencies.chatStreamService.replayActiveStream(inputArguments.conversationId);
                }
            });
        };
        const completeTerminalization = (terminalState: typeof currentState): void => {
            if (hasTerminalStateMismatch(terminalState, inputArguments)) {
                settleDone();
                return;
            }

            const activeConversationId = context.dependencies.state.getCurrentConversationId();
            let optimisticSignature: string | null = null;
            let optimisticReceipt: TerminalAssistantSettlementReceipt | null = null;
            const acknowledgeTerminalPostRender = (): void => {
                context.dependencies.presentation.onTerminalPostRenderCommitted?.(inputArguments.conversationId, inputArguments.requestId);
            };
            if (context.presentationActive && activeConversationId === inputArguments.conversationId && assistantMessage !== null) {
                dropPendingStreamRender(context, assistantMessage, inputArguments.conversationId);
                context.cachedStreamingElements = null;
                const settlementArguments = { conversationId: inputArguments.conversationId, assistantMessage, activeConversationId, onPostRenderCommitted: acknowledgeTerminalPostRender };
                const signature = resolveTerminalAssistantSettlementFingerprint(context, settlementArguments);
                optimisticReceipt = settleTerminalAssistantMessageDom(context, settlementArguments);
                if (optimisticReceipt !== null) {
                    optimisticSignature = signature;
                    terminalState.terminalRenderSettled = true;
                }
            } else {
                acknowledgeTerminalPostRender();
            }

            if (
                shouldKeepStreamingUiActiveAfterTerminal(context, {
                    conversationId: inputArguments.conversationId,
                    requestId: inputArguments.requestId,
                    assistantTimestamp: inputArguments.assistantTimestamp,
                    assistantMessage,
                    status: inputArguments.status
                })
            ) {
                runAfterCanonicalSync(() => setStreamPhase(context, inputArguments.conversationId, 'starting'));
                return;
            }

            clearAfterRecovery(optimisticSignature, optimisticReceipt);
        };
        const mountPromise = currentState.currentConversationMountPromise;
        if (mountPromise !== null && context.dependencies.state.getCurrentConversationId() === inputArguments.conversationId && assistantMessage !== null) {
            const boundedMountPromise = withTimeout(mountPromise, {
                timeoutMs: TIMEOUTS.API_REQUEST,
                timeoutMessage: `Chat stream terminal mount timed out for ${inputArguments.conversationId}`
            });
            terminateHandledPromise(
                boundedMountPromise.then(
                    () => {
                        const mountedState = getConversationStreamState(context, inputArguments.conversationId);
                        if (context.disposed || mountedState === null || mountedState.terminalRenderToken !== token) {
                            settleDone();
                            return;
                        }
                        completeTerminalization(mountedState);
                    },
                    (error) => settleFailed(recoverTerminalizationFailure(error))
                )
            );
            return;
        }
        completeTerminalization(currentState);
    }, 0);
    await donePromise;
};

export const waitForRequestTerminalization = async (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; requestId: string | null; assistantTimestamp: number }): Promise<void> => {
    const state = getConversationStreamState(context, inputArguments.conversationId);
    if (!state) {
        return;
    }
    const terminalizationKey = buildTerminalizationKey({ requestId: inputArguments.requestId, assistantTimestamp: inputArguments.assistantTimestamp });
    if (state.terminalRenderTimerId !== null && (state.terminalizationPromiseKey !== terminalizationKey || state.terminalizationPromise === null)) {
        throw new Error('Chat stream terminalization is pending but the completion promise is missing.');
    }
    if (state.terminalizationPromiseKey !== terminalizationKey || state.terminalizationPromise === null) {
        return;
    }
    await state.terminalizationPromise;
};
