/* SoAI - Chat stream terminal event application [frontend/assets/ts/features/chat/chatstreamservice/streamTerminalEventApplication.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantTimelinePayload } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import { resolveLatestLoadingActivityFromTimeline } from '@features/chat/assistanteventtimeline/activityState.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { buildChatStreamServerErrorPresentation } from '@features/chat/chatstreamservice/streamErrorPresentation.ts';
import { finalizeChatStreamServerCancellation, finalizeChatStreamServerComplete, finalizeChatStreamServerError } from '@features/chat/chatstreamservice/streamTerminalizationPolicy.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

type TerminalStreamEventType = 'completed' | 'cancelled' | 'error';

const STEER_INTERRUPTED_CODE = 'steer_interrupted';

const requireTerminalLoadingActivity = (session: ChatStreamSession, eventType: TerminalStreamEventType, failProtocol: (message: string) => void): boolean => {
    const loadingActivity = resolveLatestLoadingActivityFromTimeline(session.assistantMessage.assistantEventTimeline);
    if (loadingActivity !== null) {
        return true;
    }
    failProtocol(`Chat stream protocol error: ${eventType} requires prior loading_activity.`);
    return false;
};

const applyCompletedStreamEvent = (inputArguments: { session: ChatStreamSession; runtime: StreamRuntime; payload: AssistantTimelinePayload; assistantRevision: number; failProtocol: (message: string) => void; markDone: () => void; notifyUser: boolean }): void => {
    if (!requireTerminalLoadingActivity(inputArguments.session, 'completed', inputArguments.failProtocol)) {
        return;
    }
    const usageValue = inputArguments.payload.usage ?? null;
    if (usageValue !== null) {
        inputArguments.session.assistantMessage.usage = usageValue;
        inputArguments.session.assistantMessage.promptTokens = usageValue.promptTokens;
        inputArguments.session.assistantMessage.completionTokens = usageValue.completionTokens;
        inputArguments.session.assistantMessage.totalTokens = usageValue.totalTokens;
        inputArguments.session.assistantMessage.usageSource = usageValue.usageSource;
    }
    inputArguments.session.assistantRevision = inputArguments.assistantRevision;
    finalizeChatStreamServerComplete({
        session: inputArguments.session,
        runtime: inputArguments.runtime,
        finishReason: inputArguments.payload.finishReason ?? null,
        notifyUser: inputArguments.notifyUser
    });
    inputArguments.markDone();
};

const applyCancelledStreamEvent = (inputArguments: { session: ChatStreamSession; runtime: StreamRuntime; payload: AssistantTimelinePayload; assistantRevision: number; failProtocol: (message: string) => void; markDone: () => void; notifyUser: boolean }): void => {
    const reason = inputArguments.payload.reason;
    const code = inputArguments.payload.code;
    if (!reason || !code) {
        inputArguments.failProtocol('Chat stream protocol error: cancelled requires reason and code.');
        return;
    }
    if (!requireTerminalLoadingActivity(inputArguments.session, 'cancelled', inputArguments.failProtocol)) {
        return;
    }
    if (inputArguments.session.pendingCancellation === null) {
        inputArguments.session.pendingCancellation = { reason };
    }
    inputArguments.session.assistantRevision = inputArguments.assistantRevision;
    finalizeChatStreamServerCancellation({
        session: inputArguments.session,
        runtime: inputArguments.runtime,
        notifyUser: inputArguments.notifyUser && code !== STEER_INTERRUPTED_CODE
    });
    inputArguments.markDone();
};

const applyErrorStreamEvent = (inputArguments: { session: ChatStreamSession; runtime: StreamRuntime; payload: AssistantTimelinePayload; assistantRevision: number; failProtocol: (message: string) => void; markDone: () => void; notifyUser: boolean }): void => {
    const messageText = inputArguments.payload.message;
    const code = inputArguments.payload.code;
    const referenceId = inputArguments.payload.referenceId;
    if (!messageText || !code || !referenceId) {
        inputArguments.failProtocol('Chat stream protocol error: error requires a code, message, and reference_id.');
        return;
    }
    if (!requireTerminalLoadingActivity(inputArguments.session, 'error', inputArguments.failProtocol)) {
        return;
    }
    inputArguments.session.assistantRevision = inputArguments.assistantRevision;
    const previewContract = inputArguments.payload.previewContract ?? null;
    const presentation = buildChatStreamServerErrorPresentation({ code, technicalMessage: messageText, referenceId, previewContract });
    finalizeChatStreamServerError({
        session: inputArguments.session,
        runtime: inputArguments.runtime,
        lastError: presentation.lastError,
        errorMessage: presentation.timelineMessage,
        errorCode: code,
        referenceId,
        notifyUser: inputArguments.notifyUser
    });
    inputArguments.markDone();
};

export { applyCancelledStreamEvent, applyCompletedStreamEvent, applyErrorStreamEvent };
