/* SoAI - Chat stream command error application [frontend/assets/ts/features/chat/chatstreamservice/streamRunSessionCommandErrorApplication.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { chatStreamCommandErrorConversationMatchesSession, chatStreamCommandErrorRequestMatchesSession } from '@features/chat/chatstreamservice/streamPayloadValidation.ts';
import type { ChatStreamCommandErrorEnvelope } from '@core/realtime/eventcontracts/chatStreamCommandError.ts';
import { finalizeChatStreamCommandCancelNotFound } from '@features/chat/chatstreamservice/streamTerminalizationPolicy.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

const log = createModuleLogger('ChatStreamService', { defaultLevel: 'warn' });

type FailProtocol = (message: string, errorCode?: string | null, errorPayload?: JsonValue | null) => void;
const applyChatStreamCommandErrorEnvelope = (inputArguments: { envelope: ChatStreamCommandErrorEnvelope; session: ChatStreamSession; runtime: StreamRuntime; failProtocol: FailProtocol; markDone: () => void; isDone: () => boolean }): void => {
    if (inputArguments.isDone()) {
        return;
    }
    const envelope = inputArguments.envelope;
    if (!chatStreamCommandErrorConversationMatchesSession(envelope, inputArguments.session)) {
        return;
    }
    const phase = envelope.phase.trim();
    const errorMessage = envelope.message.trim();
    const errorCode = envelope.code.trim();
    if (!errorMessage || !errorCode) {
        return;
    }
    if (!chatStreamCommandErrorRequestMatchesSession(envelope, inputArguments.session)) {
        log('warn', 'Chat stream command error request_id mismatch; ignoring for active session', {
            convId: inputArguments.session.conversationId,
            sessionRequestId: inputArguments.session.requestId.trim(),
            receivedRequestId: envelope.requestId.trim(),
            phase,
            code: errorCode
        });
        return;
    }
    if (phase === 'cancel' && errorCode === 'not_found_error') {
        if (inputArguments.session.pendingCancellation === null) {
            inputArguments.session.pendingCancellation = { reason: errorMessage };
        }
        finalizeChatStreamCommandCancelNotFound({
            session: inputArguments.session,
            runtime: inputArguments.runtime
        });
        inputArguments.markDone();
        return;
    }
    inputArguments.failProtocol(errorMessage, errorCode, envelope);
};

export { applyChatStreamCommandErrorEnvelope };
