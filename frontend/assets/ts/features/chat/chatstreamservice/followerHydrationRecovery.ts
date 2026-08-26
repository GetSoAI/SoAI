/* SoAI - Follower chat stream hydration recovery policy [frontend/assets/ts/features/chat/chatstreamservice/followerHydrationRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChatStreamHydrationSession } from '@features/chat/chatstreamservice/streamHydrationSession.ts';

type FollowerRecoveryFailure = (message: string, errorCode?: string | null, errorPayload?: JsonValue | null) => void;
type FollowerRecoveryReconcileRequest = (convId: string) => void;

const log = createModuleLogger('ChatStreamFollowerCoordinator', { defaultLevel: 'warn' });

const requestFollowerHydrationRecovery = (inputArguments: { hydration: ChatStreamHydrationSession; receivedSequence: number; convId: string; requestReconcile: FollowerRecoveryReconcileRequest | null; failProtocol: FollowerRecoveryFailure }): void => {
    void inputArguments.hydration
        .request(inputArguments.receivedSequence)
        .then((result) => {
            if (result.status !== 'recoverable') {
                return;
            }
            log('warn', 'Stream hydration exhausted; requesting active-status reconciliation', { convId: inputArguments.convId, requiredSequence: result.requiredSequence, progressRevision: result.progressRevision });
            inputArguments.requestReconcile?.(inputArguments.convId);
        })
        .catch((error) => {
            const runtimeError = ensureError(error);
            log('warn', 'Stream hydration failed', { convId: inputArguments.convId, error: runtimeError });
            inputArguments.failProtocol(`Stream hydration failed: ${runtimeError.message}`, 'stream_hydration_failed');
        });
};

export { requestFollowerHydrationRecovery };
export type { FollowerRecoveryReconcileRequest };
