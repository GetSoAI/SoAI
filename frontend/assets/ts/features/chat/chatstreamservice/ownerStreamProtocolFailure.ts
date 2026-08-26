/* SoAI - Owner chat stream protocol failure policy [frontend/assets/ts/features/chat/chatstreamservice/ownerStreamProtocolFailure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { requestChatStreamCancel } from '@features/chat/chatstreamservice/streamCancel.ts';
import { finalizeChatStreamProtocolFailure } from '@features/chat/chatstreamservice/streamTerminalizationPolicy.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

type OwnerStreamProtocolFailure = (message: string, errorCode?: string | null, errorPayload?: JsonValue | null, cancelReason?: string | null) => void;

const createOwnerStreamProtocolFailure = (inputArguments: { session: ChatStreamSession; runtime: StreamRuntime; hasSharedStreamState: () => boolean; isDone: () => boolean; markDone: () => void }): OwnerStreamProtocolFailure => {
    return (message: string, errorCode: string | null | undefined = null, errorPayload: JsonValue | null = null, cancelReason: string | null = message): void => {
        if (inputArguments.isDone()) {
            return;
        }
        if (inputArguments.hasSharedStreamState() && cancelReason !== null) {
            requestChatStreamCancel(inputArguments.session, cancelReason, false);
        }
        finalizeChatStreamProtocolFailure({
            session: inputArguments.session,
            runtime: inputArguments.runtime,
            message,
            errorCode,
            errorPayload
        });
        inputArguments.markDone();
    };
};

export { createOwnerStreamProtocolFailure };
export type { OwnerStreamProtocolFailure };
