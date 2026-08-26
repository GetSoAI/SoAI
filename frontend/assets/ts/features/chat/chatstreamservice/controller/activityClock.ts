/* SoAI - Chat feature activity clock [frontend/assets/ts/features/chat/chatstreamservice/controller/activityClock.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatStreamingControllerContext, ConversationStreamState, StreamUpdate } from '@features/chat/chatstreamservice/controller/types.ts';
import { scheduleStaleGuardedTimeout } from '@core/timers/staleGuardedTimeout.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { clearActivityRefreshTimer } from '@features/chat/chatstreamservice/controller/state.ts';
import { recoverInactiveStreamingUi } from '@features/chat/chatstreamservice/controller/inactiveStreamUiRecovery.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { StreamRenderPatchType } from '@features/chat/stream/streamRenderPatchType.ts';

const isAssistantMessage = (message: ChatMessage): boolean => {
    return message.role === 'assistant';
};

const isActivityClockStreamActive = (context: ChatStreamingControllerContext, conversationId: string, state: ConversationStreamState | null): boolean => {
    return context.dependencies.chatStreamService.isStreaming(conversationId) || (state !== null && state.phase === 'streaming');
};

const messageMatchesActiveStream = (message: ChatMessage, state: ConversationStreamState | null): boolean => {
    if (!isAssistantMessage(message)) {
        return false;
    }
    const assistantTimestamp = state?.assistantTimestamp ?? null;
    if (assistantTimestamp === null) {
        return true;
    }
    if (message.timestamp === assistantTimestamp) {
        return true;
    }
    return message.assistantTurnAtMs === assistantTimestamp;
};

const shouldRefreshStreamActivityClock = (state: ConversationStreamState, updateStatus: StreamUpdate['status'], patchType: StreamRenderPatchType): boolean => {
    if (state.phase === 'stopping' && updateStatus === 'streaming') {
        return false;
    }
    if (state.activityRefreshTimerId === null) {
        return true;
    }
    return patchType === 'timeline-activity' || patchType === 'both' || patchType === 'terminal';
};

const resolveVisibleStreamingAssistantMessage = (context: ChatStreamingControllerContext, conversationId: string, state: ConversationStreamState | null): ChatMessage | null => {
    const conversation = context.dependencies.conversations.get(conversationId);
    const messages = conversation?.messages;
    if (!messages) {
        return null;
    }
    for (let index = messages.length - 1; index >= 0; index -= 1) {
        const message = messages[index];
        if (!isChatMessage(message) || !messageMatchesActiveStream(message, state)) {
            continue;
        }
        return message;
    }
    return null;
};

const refreshActivityClock = (context: ChatStreamingControllerContext, message: ChatMessage | null, conversationId: string): void => {
    clearActivityRefreshTimer(context, conversationId);
    if (context.disposed || !context.presentationActive) {
        return;
    }
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return;
    }
    const currentConversationId = normalizeConversationId(context.dependencies.state.getCurrentConversationId());
    if (!currentConversationId || currentConversationId !== normalizedConversationId) {
        return;
    }
    const state = context.streamStateByConversationId.get(normalizedConversationId) ?? null;
    if (!isActivityClockStreamActive(context, normalizedConversationId, state)) {
        return;
    }
    if (state === null) {
        return;
    }
    if (!message) {
        return;
    }
    if (!messageMatchesActiveStream(message, state)) {
        return;
    }
    const refreshDelayMs = context.dependencies.messageManager.resolveRunningActivityRefreshDelayMs(message, serverEpochMs());
    if (refreshDelayMs === null) {
        return;
    }
    scheduleActivityClockTick(context, {
        assistantTimestamp: state.assistantTimestamp,
        conversationId,
        normalizedConversationId,
        requestId: state.requestId,
        state,
        refreshDelayMs
    });
};

const scheduleActivityClockTick = (
    context: ChatStreamingControllerContext,
    inputArguments: {
        assistantTimestamp: number | null;
        conversationId: string;
        normalizedConversationId: string;
        requestId: string | null;
        state: ConversationStreamState;
        refreshDelayMs: number;
    }
): void => {
    const isStale = (): boolean => {
        if (context.disposed || !context.presentationActive) {
            return true;
        }
        const currentState = context.streamStateByConversationId.get(inputArguments.normalizedConversationId);
        if (currentState === undefined) {
            return true;
        }
        if (currentState !== inputArguments.state || currentState.requestId !== inputArguments.requestId || currentState.assistantTimestamp !== inputArguments.assistantTimestamp) {
            return true;
        }
        if (!isActivityClockStreamActive(context, inputArguments.normalizedConversationId, currentState)) {
            return true;
        }
        const activeConversationId = normalizeConversationId(context.dependencies.state.getCurrentConversationId());
        if (!activeConversationId || activeConversationId !== inputArguments.normalizedConversationId) {
            return true;
        }
        return false;
    };
    inputArguments.state.activityRefreshTimerId = scheduleStaleGuardedTimeout({
        currentTimerId: inputArguments.state.activityRefreshTimerId,
        clearTimer: (timerId) => {
            if (timerId === null || timerId === undefined) {
                return;
            }
            context.timers.clearTimeout(timerId);
        },
        setTimer: (functionValue, delayMs) => context.timers.setTimeout(functionValue, delayMs),
        delayMs: inputArguments.refreshDelayMs,
        isStale,
        onTick: () => {
            inputArguments.state.activityRefreshTimerId = null;
            if (isStale()) {
                return;
            }
            if (!context.dependencies.chatStreamService.isStreaming(inputArguments.normalizedConversationId)) {
                terminateHandledPromise(recoverInactiveStreamingUi(context, inputArguments.normalizedConversationId, inputArguments.state));
                return;
            }
            const message = resolveVisibleStreamingAssistantMessage(context, inputArguments.conversationId, inputArguments.state);
            if (message === null) {
                return;
            }
            if (!isStale()) {
                const refreshDelayMs = context.dependencies.messageManager.resolveRunningActivityRefreshDelayMs(message, serverEpochMs());
                if (refreshDelayMs !== null) {
                    scheduleActivityClockTick(context, {
                        ...inputArguments,
                        refreshDelayMs
                    });
                }
            }
        }
    });
};

const refreshCurrentConversationActivityClock = (context: ChatStreamingControllerContext): void => {
    const conversationId = normalizeConversationId(context.dependencies.state.getCurrentConversationId());
    if (!conversationId) {
        return;
    }
    const state = context.streamStateByConversationId.get(conversationId) ?? null;
    if (!isActivityClockStreamActive(context, conversationId, state)) {
        clearActivityRefreshTimer(context, conversationId);
        return;
    }
    refreshActivityClock(context, resolveVisibleStreamingAssistantMessage(context, conversationId, state), conversationId);
};

export { refreshActivityClock, refreshCurrentConversationActivityClock, shouldRefreshStreamActivityClock };
