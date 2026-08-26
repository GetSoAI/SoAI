/* SoAI - Chat feature streaming controller [frontend/assets/ts/features/chat/chatstreamservice/controller/ChatStreamingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { waitForConversationIdleState } from '@features/chat/chatstreamservice/controller/idleWaiters.ts';
import { stopStreaming } from '@features/chat/chatstreamservice/controller/actions/stopStreaming.ts';
import { interruptActiveStreamForConversation } from '@features/chat/chatstreamservice/controller/actions/streamCancellation.ts';
import { streamResponse } from '@features/chat/chatstreamservice/controller/actions/streamResponse.ts';
import { refreshCurrentConversationActivityClock } from '@features/chat/chatstreamservice/controller/activityClock.ts';
import { handleServiceUpdate } from '@features/chat/chatstreamservice/controller/serviceUpdates.ts';
import { createChatStreamingControllerContext, disposeContext, getConversationStreamState, isConversationStreamingUiActive, isTerminalRenderPendingForMessage, reconcileInactiveSyncedConversation, requireConversationStreamState, requireScheduleStreamRender, suspendPresentationContext } from '@features/chat/chatstreamservice/controller/state.ts';
import { waitForTerminalReconciliation } from '@features/chat/chatstreamservice/controller/terminalizationState.ts';
import { buildTurnAdmissionSnapshot, resolveSyncedTurnAdmissionSnapshot } from '@features/chat/chatstreamservice/controller/turnAdmission.ts';
import type { ChatStreamingControllerContext, ChatStreamingControllerDependencies, ChatStreamingControllerOptions, ChatStreamingControllerState, ChatStreamResponseOptions, StreamUpdate } from '@features/chat/chatstreamservice/controller/types.ts';
import type { ChatStreamLifecycle, ChatStreamStartAdmission, ChatStreamStopOptions, ChatTurnAdmissionSnapshot, ChatTurnAdmissionStreamIdentity, StreamListener } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import { createAbortSignalScope, isAbortError } from '@core/errors/abort.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import { CHAT_STREAM_CANCEL_TIMEOUT_MS } from '@features/chat/chatstreamservice/streamCancel.ts';

class ChatStreamingController {
    readonly #context: ChatStreamingControllerContext;
    readonly #releaseConversationTitleResolver: () => void;

    constructor(dependencies: ChatStreamingControllerDependencies, options: ChatStreamingControllerOptions = {}) {
        this.#context = createChatStreamingControllerContext(dependencies, options);

        const streamRenderRuntime = dependencies.createStreamRenderRuntime(this.#context);
        this.#context.scheduleStreamRender = streamRenderRuntime.scheduleStreamRender;
        this.#context.reconcileActivityDurations = streamRenderRuntime.reconcileActivityDurations;
        const conversationTitleResolver = (conversationId: string): string | null => {
            const conversation = dependencies.conversations.get(conversationId);
            const title = conversation?.title;
            return isString(title) && title.trim() ? title.trim() : null;
        };
        this.#releaseConversationTitleResolver = dependencies.chatStreamService.setConversationTitleResolver(conversationTitleResolver);

        this.#context.serviceUnsubscribe = this.#context.dependencies.chatStreamService.subscribe(async (update: StreamUpdate): Promise<void> => {
            if (this.#context.disposed) {
                return;
            }
            await handleServiceUpdate(this.#context, update);
        });
        requireScheduleStreamRender(this.#context);
    }

    dispose(): void {
        this.#releaseConversationTitleResolver();
        disposeContext(this.#context);
    }

    resumePresentation(): void {
        if (this.#context.disposed) {
            throw new Error('Cannot resume a disposed Chat streaming presentation');
        }
        this.#context.presentationGeneration += 1;
        this.#context.presentationActive = true;
    }

    suspendPresentation(): void {
        suspendPresentationContext(this.#context);
    }

    async streamResponse(conversation: ConversationContract, options: ChatStreamResponseOptions = {}): Promise<void> {
        await streamResponse(this.#context, conversation, options);
    }

    stopStreaming(options: ChatStreamStopOptions = {}): void {
        stopStreaming(this.#context, options);
    }

    interruptStreaming(conversationId: string, reason?: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        interruptActiveStreamForConversation(this.#context, normalizedConversationId, reason);
    }

    async syncConversationStatus(conversationId: string): Promise<void> {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        await this.#context.dependencies.chatStreamService.syncSelectedConversationStatus(normalizedConversationId);
        reconcileInactiveSyncedConversation(this.#context, normalizedConversationId);
    }

    async reconcileConversationInputSettlement(conversationId: string): Promise<void> {
        const presentationGeneration = this.#context.presentationGeneration;
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId || this.#context.disposed || !this.#context.presentationActive) {
            return;
        }
        const isCurrentConversation = normalizeConversationId(this.#context.dependencies.state.getCurrentConversationId()) === normalizedConversationId;
        if (isCurrentConversation && this.#context.presentationActive) {
            await this.#context.dependencies.storageManager.loadConversationMessages(normalizedConversationId, {
                force: true,
                mergeStreamingAssistants: true
            });
            if (this.#context.disposed || !this.#context.presentationActive || this.#context.presentationGeneration !== presentationGeneration || normalizeConversationId(this.#context.dependencies.state.getCurrentConversationId()) !== normalizedConversationId) {
                return;
            }
            this.#context.dependencies.presentation.invalidateChatMarkup('current');
            await this.#context.dependencies.presentation.renderCurrentConversation();
        }
        await this.#context.dependencies.chatStreamService.syncConversationStatus(normalizedConversationId);
        if (this.#context.disposed || !this.#context.presentationActive || this.#context.presentationGeneration !== presentationGeneration) {
            return;
        }
        reconcileInactiveSyncedConversation(this.#context, normalizedConversationId);
        if (this.#context.presentationActive && isCurrentConversation && normalizeConversationId(this.#context.dependencies.state.getCurrentConversationId()) === normalizedConversationId) {
            this.#context.dependencies.presentation.invalidateChatMarkup('current');
            await this.#context.dependencies.presentation.renderCurrentConversation();
        }
    }

    async resolveStartAdmission(conversationId: string, signal?: AbortSignal | null): Promise<ChatStreamStartAdmission> {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return 'unknown';
        }
        return (await this.resolveSyncedTurnAdmission(normalizedConversationId, signal ?? null)).startAdmission;
    }

    getCachedTurnAdmission(conversationId: string): ChatTurnAdmissionSnapshot {
        return buildTurnAdmissionSnapshot(this.#context, conversationId);
    }

    async resolveSyncedTurnAdmission(conversationId: string, signal?: AbortSignal | null): Promise<ChatTurnAdmissionSnapshot> {
        return resolveSyncedTurnAdmissionSnapshot(this.#context, conversationId, signal ?? null);
    }

    async waitForConversationIdle(conversationId: string, signal?: AbortSignal | null): Promise<void> {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            throw new Error('Chat stream idle wait requires a valid conversation id.');
        }
        await waitForConversationIdleState({
            waiters: this.#context.idleWaitersByConversationId,
            conversationId: normalizedConversationId,
            signal: signal ?? null,
            isIdle: () => !isConversationStreamingUiActive(this.#context, normalizedConversationId)
        });
    }

    async waitForConversationRequestExit(conversationId: string, requestId: string, signal?: AbortSignal | null): Promise<void> {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const normalizedRequestId = requestId.trim();
        if (!normalizedConversationId || !normalizedRequestId) {
            throw new Error('Chat stream request exit wait requires a valid conversation and request id.');
        }
        const timeoutController = new AbortController();
        const timeoutTimer = new TimeoutTimer(CHAT_STREAM_CANCEL_TIMEOUT_MS, () => timeoutController.abort());
        const signalScope = createAbortSignalScope([signal ?? null, timeoutController.signal]);
        timeoutTimer.start();
        try {
            await waitForConversationIdleState({
                waiters: this.#context.idleWaitersByConversationId,
                conversationId: normalizedConversationId,
                signal: signalScope.signal,
                isIdle: () => {
                    const stateRequestId = getConversationStreamState(this.#context, normalizedConversationId)?.requestId ?? null;
                    const serviceRequestId = this.#context.dependencies.chatStreamService.getStreamIdentity(normalizedConversationId)?.requestId ?? null;
                    return stateRequestId !== normalizedRequestId && serviceRequestId !== normalizedRequestId;
                }
            });
        } catch (error) {
            if (timeoutController.signal.aborted && signal?.aborted !== true && isAbortError(error)) {
                throw new Error('Chat stream cancellation reconciliation timed out.');
            }
            throw error;
        } finally {
            timeoutTimer.stop();
            signalScope.cleanup();
        }
    }

    async waitForTerminalReconciliation(conversationId: string, signal?: AbortSignal | null): Promise<void> {
        await waitForTerminalReconciliation(this.#context, conversationId, signal ?? null);
    }

    refreshCurrentConversationActivityClock(): void {
        const conversationId = normalizeConversationId(this.#context.dependencies.state.getCurrentConversationId());
        if (conversationId && this.#context.dependencies.chatStreamService.isStreaming(conversationId)) {
            requireConversationStreamState(this.#context, conversationId);
        }
        refreshCurrentConversationActivityClock(this.#context);
    }

    isStreamingConversation(conversationId: string): boolean {
        return isConversationStreamingUiActive(this.#context, conversationId);
    }

    isTerminalRenderPending(conversationId: string, message: ChatMessage): boolean {
        return isTerminalRenderPendingForMessage(this.#context, conversationId, message);
    }

    canQueueConversationInput(conversationId: string): boolean {
        return this.#context.dependencies.chatStreamService.canQueueConversationInput(conversationId);
    }

    canSteerConversationInput(conversationId: string): boolean {
        return this.#context.dependencies.chatStreamService.canSteerConversationInput(conversationId);
    }

    canStartPromptNow(conversationId: string): boolean {
        return this.#context.dependencies.chatStreamService.canStartPromptNow(conversationId);
    }

    getStreamLifecycle(conversationId: string): ChatStreamLifecycle {
        return this.#context.dependencies.chatStreamService.getStreamLifecycle(conversationId);
    }

    getStreamIdentity(conversationId: string | null): ChatTurnAdmissionStreamIdentity | null {
        return this.#context.dependencies.chatStreamService.getStreamIdentity(conversationId);
    }

    subscribeStreamUpdates(listener: StreamListener): () => void {
        return this.#context.dependencies.chatStreamService.subscribe(listener);
    }

    scheduleTimelineActivityRender(message: ChatMessage, conversationId: string): void {
        requireScheduleStreamRender(this.#context)({ message, conversationId, patchType: 'timeline-activity', assistantRevision: null, textAppend: null });
    }

    hasActiveComparisonRun(conversationId: string): boolean {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return false;
        }
        const state = getConversationStreamState(this.#context, normalizedConversationId);
        if (!state || state.phase === 'idle') {
            return false;
        }
        const run = state.comparisonRun;
        if (!run) {
            return false;
        }
        return run.variantCount > 1;
    }

    getActiveComparisonRun(conversationId: string): { assistantTurnTimestamp: number; variantCount: number } | null {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return null;
        }
        const state = getConversationStreamState(this.#context, normalizedConversationId);
        if (!state || state.phase === 'idle') {
            return null;
        }
        const run = state.comparisonRun;
        if (!run || run.variantCount <= 1) {
            return null;
        }
        return {
            assistantTurnTimestamp: run.assistantTurnTimestamp,
            variantCount: run.variantCount
        };
    }
}

export { ChatStreamingController };
export type { ChatStreamingControllerDependencies, ChatStreamingControllerState };
