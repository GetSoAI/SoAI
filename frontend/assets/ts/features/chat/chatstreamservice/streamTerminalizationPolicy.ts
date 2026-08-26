/* SoAI - Chat stream terminalization policy [frontend/assets/ts/features/chat/chatstreamservice/streamTerminalizationPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { buildChatStreamClientErrorPresentation, buildChatStreamServerErrorPresentation, isChatStreamClientErrorCode, isChatStreamServerErrorCode } from '@features/chat/chatstreamservice/streamErrorPresentation.ts';
import { finalizeChatStreamTerminalState, type TerminalSessionStatus } from '@features/chat/chatstreamservice/streamTerminalState.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { resolveLatestTerminalTimelineError } from '@features/chat/chatstreamservice/streamRunSessionTerminalError.ts';

type TerminalPolicyArguments = {
    session: ChatStreamSession;
    runtime: StreamRuntime;
};

const finalizeChatStreamOwnerCancellation = (inputArguments: TerminalPolicyArguments & { notifyUser: boolean }): void => {
    finalizeChatStreamTerminalState({
        session: inputArguments.session,
        runtime: inputArguments.runtime,
        status: 'cancelled',
        finishReason: 'cancelled',
        lastError: null,
        errorMessage: null,
        errorCode: null,
        referenceId: null,
        notifyUser: inputArguments.notifyUser
    });
};

const finalizeChatStreamCommandCancelNotFound = (inputArguments: TerminalPolicyArguments): void => {
    finalizeChatStreamOwnerCancellation({
        session: inputArguments.session,
        runtime: inputArguments.runtime,
        notifyUser: true
    });
};

const finalizeChatStreamServerComplete = (inputArguments: TerminalPolicyArguments & { finishReason: string | null; notifyUser: boolean }): void => {
    finalizeChatStreamTerminalState({
        session: inputArguments.session,
        runtime: inputArguments.runtime,
        status: 'complete',
        finishReason: inputArguments.finishReason,
        lastError: null,
        errorMessage: null,
        errorCode: null,
        referenceId: null,
        notifyUser: inputArguments.notifyUser
    });
};

const finalizeChatStreamServerCancellation = (inputArguments: TerminalPolicyArguments & { notifyUser: boolean }): void => {
    finalizeChatStreamOwnerCancellation({
        session: inputArguments.session,
        runtime: inputArguments.runtime,
        notifyUser: inputArguments.notifyUser
    });
};

const finalizeChatStreamServerError = (inputArguments: TerminalPolicyArguments & { lastError: JsonValue; errorMessage: string; errorCode: string; referenceId: string; notifyUser: boolean }): void => {
    finalizeChatStreamTerminalState({
        session: inputArguments.session,
        runtime: inputArguments.runtime,
        status: 'error',
        finishReason: 'error',
        lastError: inputArguments.lastError,
        errorMessage: inputArguments.errorMessage,
        errorCode: inputArguments.errorCode,
        referenceId: inputArguments.referenceId,
        notifyUser: inputArguments.notifyUser
    });
};

const finalizeChatStreamHydratedTerminal = (inputArguments: TerminalPolicyArguments & { status: TerminalSessionStatus; finishReason: string | null; notifyUser: boolean }): void => {
    const timelineError = inputArguments.status === 'error' ? resolveLatestTerminalTimelineError(inputArguments.session.assistantMessage.assistantEventTimeline) : null;
    const presentation = timelineError !== null ? buildChatStreamServerErrorPresentation({ code: timelineError.code, technicalMessage: timelineError.message, referenceId: timelineError.referenceId, ...(timelineError.previewContract !== undefined ? { previewContract: timelineError.previewContract } : {}) }) : null;
    finalizeChatStreamTerminalState({
        session: inputArguments.session,
        runtime: inputArguments.runtime,
        status: inputArguments.status,
        finishReason: inputArguments.finishReason,
        lastError: presentation?.lastError ?? null,
        errorMessage: presentation?.timelineMessage ?? null,
        errorCode: timelineError?.code ?? null,
        referenceId: timelineError?.referenceId ?? null,
        notifyUser: inputArguments.notifyUser
    });
};

const finalizeChatStreamProtocolFailure = (inputArguments: TerminalPolicyArguments & { message: string; errorCode?: string | null | undefined; errorPayload?: JsonValue | null }): void => {
    const normalizedCode = optionalTrimmedString(inputArguments.errorCode);
    const code = normalizedCode ?? 'protocol_error';
    if (isChatStreamClientErrorCode(code)) {
        const presentation = buildChatStreamClientErrorPresentation({ code, technicalMessage: inputArguments.message });
        finalizeChatStreamTerminalState({
            session: inputArguments.session,
            runtime: inputArguments.runtime,
            status: 'error',
            finishReason: 'error',
            lastError: presentation.lastError,
            errorMessage: presentation.timelineMessage,
            errorCode: code,
            referenceId: inputArguments.session.requestId,
            notifyUser: true
        });
        return;
    }
    if (isChatStreamServerErrorCode(code)) {
        const presentation = buildChatStreamServerErrorPresentation({ code, technicalMessage: inputArguments.message, referenceId: inputArguments.session.requestId });
        finalizeChatStreamTerminalState({
            session: inputArguments.session,
            runtime: inputArguments.runtime,
            status: 'error',
            finishReason: 'error',
            lastError: inputArguments.errorPayload ?? presentation.lastError,
            errorMessage: presentation.timelineMessage,
            errorCode: code,
            referenceId: inputArguments.session.requestId,
            notifyUser: true
        });
        return;
    }
    finalizeChatStreamTerminalState({
        session: inputArguments.session,
        runtime: inputArguments.runtime,
        status: 'error',
        finishReason: 'error',
        lastError: inputArguments.errorPayload ?? { message: inputArguments.message, code },
        errorMessage: inputArguments.message,
        errorCode: code,
        referenceId: inputArguments.session.requestId,
        notifyUser: true
    });
};

export { finalizeChatStreamCommandCancelNotFound, finalizeChatStreamHydratedTerminal, finalizeChatStreamOwnerCancellation, finalizeChatStreamProtocolFailure, finalizeChatStreamServerCancellation, finalizeChatStreamServerComplete, finalizeChatStreamServerError };
