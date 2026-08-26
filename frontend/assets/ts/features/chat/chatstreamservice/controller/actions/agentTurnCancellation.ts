/* SoAI - Chat feature agent turn cancellation [frontend/assets/ts/features/chat/chatstreamservice/controller/actions/agentTurnCancellation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isString } from '@core/typeGuards.ts';
import type { ChatStreamingControllerContext } from '@features/chat/chatstreamservice/controller/types.ts';

const requestAgentTurnCancellation = (context: ChatStreamingControllerContext, conversationId: string, forcePendingSteers: boolean): void => {
    const resolveTurnId = context.dependencies.resolveAgentRunningTurnId;
    const cancelAgentTurn = context.dependencies.cancelAgentTurn;
    if (!resolveTurnId || !cancelAgentTurn) {
        return;
    }
    const turnId = resolveTurnId(conversationId);
    if (!isString(turnId) || !turnId.trim()) {
        return;
    }
    void cancelAgentTurn(conversationId, turnId.trim(), { forcePendingSteers }).then(
        (): void => undefined,
        (error) => {
            context.errorHandler?.debug?.('ChatStream', 'Failed to cancel active agent turn', ensureError(error));
        }
    );
};

export { requestAgentTurnCancellation };
