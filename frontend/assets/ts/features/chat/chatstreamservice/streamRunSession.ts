/* SoAI - Chat feature stream run session [frontend/assets/ts/features/chat/chatstreamservice/streamRunSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { getUserCancellationReason } from '@core/tasks/cancellationReasons.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ContentPreviewFeedbackPayload, PreviewContractViolationFeedbackPayload } from '@features/chat/contentPreviewContracts.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamSession, HydratedSnapshotApplicationResult } from '@features/chat/chatstreamservice/types.ts';
import type { ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import { requestChatStreamCancel } from '@features/chat/chatstreamservice/streamCancel.ts';
import { createChatStreamEventPump, type SequenceMismatchPolicy } from '@features/chat/chatstreamservice/streamRunSessionEventPump.ts';
import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import type { ChatStreamCommandErrorEnvelope } from '@core/realtime/eventcontracts/chatStreamCommandError.ts';
import { ChatStreamHydrationSession, buildDefaultFetchStreamState } from '@features/chat/chatstreamservice/streamHydrationSession.ts';
import { bindOwnerStreamSessionLifecycle, type OwnerStreamSessionLifecycle } from '@features/chat/chatstreamservice/streamRunSessionLifecycle.ts';
import { buildChatStreamStartPayload } from '@features/chat/chatstreamservice/streamStartPayload.ts';
import { sendChatStreamStartPayload } from '@features/chat/chatstreamservice/streamStartSender.ts';
import { bindChatStreamOwnerRelease, releaseChatStreamOwnerLocally, shouldReleaseChatStreamOwnerLocally } from '@features/chat/chatstreamservice/streamOwnerRelease.ts';
import { finalizeChatStreamOwnerCancellation } from '@features/chat/chatstreamservice/streamTerminalizationPolicy.ts';
import { createOwnerStreamProtocolFailure } from '@features/chat/chatstreamservice/ownerStreamProtocolFailure.ts';

const log = createModuleLogger('ChatStreamService', { defaultLevel: 'warn' });
const STREAM_START_TIMEOUT_MS = 15000;
const CANCEL_WATCHDOG_MS = 12000;

interface RunStreamSessionOptions {
    apiClient?: ChatStreamApiClient | null;
    syncActiveStatusAfterOwnerRelease?: (conversationId: string) => Promise<void>;
}

const runStreamSession = async (session: ChatStreamSession, requestBody: JsonObject, contentPreviewFeedback: ContentPreviewFeedbackPayload | null, previewContractFeedback: PreviewContractViolationFeedbackPayload | null, runtime: StreamRuntime, registerOwnerHandlers: (inputArguments: { conversationId: string; requestId: string; handleStreamEvent: (envelope: ChatStreamEventEnvelope) => void; handleCommandErrorEvent: (envelope: ChatStreamCommandErrorEnvelope) => void; applyHydratedSnapshot: (message: ChatMessage, notifyUserOnTerminal: boolean) => Promise<HydratedSnapshotApplicationResult> }) => () => void, options: RunStreamSessionOptions = {}): Promise<void> => {
    const apiClient = options.apiClient ?? null;
    const timers = new ResourceTracker();
    let startupTimeoutId: number | null = null;
    let cancelWatchdogId: number | null = null;
    let sharedStreamStateObserved = false;
    let done = false;
    let throwAfterFinally: Error | null = null;
    let startDispatched = false;
    let unbindOwnerRelease: (() => void) | null = null;
    const doneDeferred = createDeferred<void>();
    const donePromise = doneDeferred.promise;
    const clearStartupTimeout = (): void => {
        if (startupTimeoutId === null) {
            return;
        }
        timers.clearTimeout(startupTimeoutId);
        startupTimeoutId = null;
    };
    const clearCancelWatchdog = (): void => {
        if (cancelWatchdogId === null) {
            return;
        }
        timers.clearTimeout(cancelWatchdogId);
        cancelWatchdogId = null;
    };
    const markDone = (): void => {
        if (done) {
            return;
        }
        clearStartupTimeout();
        clearCancelWatchdog();
        done = true;
        doneDeferred.resolve();
    };
    const hasSharedStreamState = (): boolean => session.firstServerEventHandled || sharedStreamStateObserved;
    const finalizeCancellation = (): void => {
        finalizeChatStreamOwnerCancellation({
            session,
            runtime,
            notifyUser: true
        });
        markDone();
    };
    const releaseOwnerLocally = (): void => {
        releaseChatStreamOwnerLocally(session, markDone);
    };
    const failProtocol = createOwnerStreamProtocolFailure({ session, runtime, hasSharedStreamState, isDone: (): boolean => done, markDone });
    const onMatchedStreamEvent = async (): Promise<void> => {
        sharedStreamStateObserved = true;
        session.countsAsStreaming = true;
        clearStartupTimeout();
    };
    const markHydratedStreamState = (): void => {
        sharedStreamStateObserved = true;
        session.countsAsStreaming = true;
        clearStartupTimeout();
    };
    let hydrationSession: ChatStreamHydrationSession | null = null;
    const sequenceMismatchPolicy: SequenceMismatchPolicy | null =
        apiClient === null
            ? null
            : {
                  decide: ({ receivedSequence }): { action: 'pause' } => {
                      if (hydrationSession === null) {
                          failProtocol('Stream hydration failed: owner hydration is not initialized.', 'stream_hydration_failed');
                          return { action: 'pause' };
                      }
                      void hydrationSession
                          .request(receivedSequence)
                          .then((result) => {
                              if (result.status !== 'recoverable') {
                                  return;
                              }
                              lifecycle?.reconcile();
                          })
                          .catch((error) => {
                              const runtimeError = ensureError(error);
                              log('warn', 'Owner stream hydration failed', { convId: session.conversationId, error: runtimeError });
                              failProtocol(`Stream hydration failed: ${runtimeError.message}`, 'stream_hydration_failed');
                          });
                      return { action: 'pause' };
                  }
              };
    let lifecycle: OwnerStreamSessionLifecycle | null = null;
    try {
        const eventPump = createChatStreamEventPump({
            session,
            runtime,
            failProtocol,
            markDone,
            isDone: (): boolean => done,
            onMatchedStreamEvent,
            markThrowAfterFinally: (error: Error): void => {
                throwAfterFinally = error;
            },
            sequenceMismatchPolicy
        });
        if (apiClient !== null) {
            hydrationSession = new ChatStreamHydrationSession({
                convId: session.conversationId,
                session,
                pump: eventPump,
                fetchStreamState: buildDefaultFetchStreamState(apiClient, null),
                onSharedStreamState: markHydratedStreamState
            });
        }
        const handleDisconnected = (): void => {
            if (done) {
                return;
            }
            if (shouldReleaseChatStreamOwnerLocally(session)) {
                if (startDispatched) releaseOwnerLocally();
                return;
            }
            if (session.abortController.signal.aborted) {
                return;
            }
            if (hasSharedStreamState()) {
                clearStartupTimeout();
                runtime.notify(session, { type: 'replay' });
                return;
            }
            failProtocol('Chat stream interrupted: WebSocket disconnected.', 'ws_disconnected');
        };
        const resolveAbortCancellation = (): { reason: string; forcePendingSteers: boolean } => {
            const cancellation = session.pendingCancellation;
            if (cancellation !== null && isString(cancellation.reason) && cancellation.reason.trim()) {
                return {
                    reason: cancellation.reason.trim(),
                    forcePendingSteers: cancellation.forcePendingSteers === true
                };
            }
            const defaulted = { reason: getUserCancellationReason(), forcePendingSteers: false };
            session.pendingCancellation = defaulted;
            return defaulted;
        };
        const abortListener = (): void => {
            if (done) {
                return;
            }
            if (session.stopOperationPending === true) {
                releaseOwnerLocally();
                return;
            }
            if (shouldReleaseChatStreamOwnerLocally(session)) {
                releaseOwnerLocally();
                return;
            }
            if (session.status !== 'streaming') {
                markDone();
                return;
            }
            const cancellation = resolveAbortCancellation();
            if (!startDispatched) {
                return;
            }
            clearStartupTimeout();
            if (!hasSharedStreamState()) {
                finalizeCancellation();
            } else {
                cancelWatchdogId = timers.setTimeout((): void => {
                    if (done) {
                        return;
                    }
                    finalizeCancellation();
                }, CANCEL_WATCHDOG_MS);
            }
            requestChatStreamCancel(session, cancellation.reason, cancellation.forcePendingSteers === true);
        };
        lifecycle = bindOwnerStreamSessionLifecycle({
            apiClient,
            session,
            runtime,
            registerOwnerHandlers,
            handleStreamEvent: eventPump.handleStreamEnvelope,
            handleCommandErrorEvent: eventPump.handleCommandErrorEnvelope,
            applyHydratedSnapshot: async (message: ChatMessage, notifyUserOnTerminal: boolean): Promise<HydratedSnapshotApplicationResult> => await eventPump.applyHydratedSnapshot(message, { resume: true, onSharedStreamState: markHydratedStreamState, notifyUserOnTerminal }),
            hydrationSession: () => hydrationSession,
            hasSharedStreamState,
            failProtocol,
            markDone,
            handleAbort: abortListener,
            handleDisconnected,
            syncActiveStatusAfterOwnerRelease: options.syncActiveStatusAfterOwnerRelease ?? null
        });
        unbindOwnerRelease = bindChatStreamOwnerRelease(session, () => {
            if (!done && startDispatched) releaseOwnerLocally();
        });
        const startPayload = buildChatStreamStartPayload({ session, requestBody, contentPreviewFeedback, previewContractFeedback });
        const startOutcome = await sendChatStreamStartPayload({ session, startPayload });
        if (startOutcome === 'sent') {
            startDispatched = true;
            if (shouldReleaseChatStreamOwnerLocally(session)) {
                releaseOwnerLocally();
            } else if (session.abortController.signal.aborted) {
                abortListener();
            } else {
                startupTimeoutId = timers.setTimeout((): void => {
                    if (done || hasSharedStreamState() || session.abortController.signal.aborted) return;
                    if (shouldReleaseChatStreamOwnerLocally(session)) {
                        releaseOwnerLocally();
                        return;
                    }
                    runtime.notify(session, { type: 'replay' });
                }, STREAM_START_TIMEOUT_MS);
            }
        }
        await donePromise;
    } catch (error) {
        if (shouldReleaseChatStreamOwnerLocally(session)) {
            releaseOwnerLocally();
            return;
        }
        if (!startDispatched && session.abortController.signal.aborted && session.pendingCancellation !== null) {
            finalizeCancellation();
            return;
        }
        if (session.status === 'cancelled') {
            markDone();
            return;
        }
        const runtimeError = ensureError(error);
        log('error', 'Chat stream start failed', { error: runtimeError });
        failProtocol(runtimeError.message, 'client_error');
    } finally {
        clearStartupTimeout();
        unbindOwnerRelease?.();
        unbindOwnerRelease = null;
        lifecycle?.cleanup();
        hydrationSession?.dispose();
        hydrationSession = null;
        session.active = false;
        timers.cleanup();
    }
    if (throwAfterFinally) {
        throw throwAfterFinally;
    }
};
export { runStreamSession };
