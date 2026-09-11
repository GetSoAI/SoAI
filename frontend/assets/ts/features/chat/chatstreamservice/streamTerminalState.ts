/* SoAI - Shared terminal-state application for chat stream sessions [frontend/assets/ts/features/chat/chatstreamservice/streamTerminalState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { settleTerminalAssistantActivities } from '@features/chat/assistanteventtimeline/terminalActivitySettlement.ts';
import { createAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { updateAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexUpdate.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { applyGenerationMetrics } from '@features/chat/chatstreamservice/streamMessageUpdates.ts';
import { writeTerminalErrorToTimeline } from '@features/chat/chatstreamservice/streamRunSessionTerminalError.ts';
import { clearChatStreamStatusPreview } from '@features/chat/chatstreamservice/streamStatusPreviewMessageState.ts';

type TerminalSessionStatus = 'complete' | 'cancelled' | 'error';

const log = createModuleLogger('ChatStreamTerminalState', { defaultLevel: 'warn' });

const applyChatStreamTerminalState = (inputArguments: { session: ChatStreamSession; status: TerminalSessionStatus; finishReason: string | null; lastError: JsonValue | null; errorMessage: string | null; errorCode: string | null; referenceId?: string | null }): void => {
    inputArguments.session.status = inputArguments.status;
    clearChatStreamStatusPreview(inputArguments.session.assistantMessage);
    if (inputArguments.finishReason !== null) {
        inputArguments.session.assistantMessage.finishReason = inputArguments.finishReason;
    }
    inputArguments.session.lastError = inputArguments.lastError;
    const activitiesSettled = settleTerminalAssistantActivities(inputArguments.session.assistantMessage, inputArguments.status, serverEpochMs());
    if (activitiesSettled) {
        inputArguments.session.assistantTimelineIndexState = createAssistantTimelineIndexState();
        updateAssistantTimelineIndexState(inputArguments.session.assistantTimelineIndexState, inputArguments.session.assistantMessage);
    }
    if (inputArguments.status === 'error' && inputArguments.errorMessage !== null) {
        writeTerminalErrorToTimeline(inputArguments.session, inputArguments.errorMessage, inputArguments.errorCode, inputArguments.referenceId ?? inputArguments.session.requestId);
    }
    applyGenerationMetrics(inputArguments.session);
};

const finalizeChatStreamTerminalState = (inputArguments: { session: ChatStreamSession; runtime: StreamRuntime; status: TerminalSessionStatus; finishReason: string | null; lastError: JsonValue | null; errorMessage: string | null; errorCode: string | null; referenceId?: string | null; notifyUser: boolean }): void => {
    applyChatStreamTerminalState(inputArguments);
    inputArguments.runtime.notify(inputArguments.session, { type: 'terminal' });
    if (!inputArguments.notifyUser) {
        return;
    }
    try {
        inputArguments.runtime.notifyUser(inputArguments.session);
    } catch (error) {
        log('warn', 'Chat stream user notification failed after terminal state publication', {
            conversationId: inputArguments.session.conversationId,
            requestId: inputArguments.session.requestId,
            error: ensureError(error)
        });
    }
};

export { applyChatStreamTerminalState, finalizeChatStreamTerminalState };
export type { TerminalSessionStatus };
