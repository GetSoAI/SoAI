/* SoAI - Owner chat stream reconnect synchronization [frontend/assets/ts/features/chat/chatstreamservice/ownerReconnectSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import { fetchChatStreamStatusSnapshot, type ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { waitForInactiveTerminalAssistantState } from '@features/chat/chatstreamservice/inactiveTerminalHydration.ts';
import { applyAssistantMessageSnapshot, sessionMatchesActiveStatus } from '@features/chat/chatstreamservice/activeStatusSessionState.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import type { ChatStreamHydrationSession } from '@features/chat/chatstreamservice/streamHydrationSession.ts';
import { finalizeChatStreamHydratedTerminal, finalizeChatStreamOwnerCancellation } from '@features/chat/chatstreamservice/streamTerminalizationPolicy.ts';
import { resolveHydratedTerminalStatus } from '@features/chat/chatstreamservice/streamHydratedTerminalStatus.ts';

type FailProtocol = (message: string, errorCode?: string | null, errorPayload?: JsonValue | null) => void;
type SyncActiveStatusAfterOwnerRelease = (conversationId: string) => Promise<void>;
type OwnerHydrationSession = Pick<ChatStreamHydrationSession, 'request'>;

interface OwnerReconnectSync {
    request(): void;
    dispose(): void;
}

const log = createModuleLogger('ChatStreamService', { defaultLevel: 'warn' });

const createOwnerReconnectSync = (inputArguments: { apiClient: ChatStreamApiClient | null; hydrationSession: () => OwnerHydrationSession | null; session: ChatStreamSession; runtime: StreamRuntime; hasSharedStreamState: () => boolean; failProtocol: FailProtocol; markDone: () => void; releaseOwnerHandlers: () => void; syncActiveStatusAfterOwnerRelease: SyncActiveStatusAfterOwnerRelease | null }): OwnerReconnectSync => {
    let syncPromise: Promise<void> | null = null;
    let disposed = false;

    const finalizeHydratedTerminalState = (): void => {
        const terminalStatus = resolveHydratedTerminalStatus(inputArguments.session);
        if (terminalStatus === null) {
            inputArguments.failProtocol('Chat stream reconnect found an inactive backend stream without terminal assistant state.', 'protocol_error');
            return;
        }
        finalizeChatStreamHydratedTerminal({
            session: inputArguments.session,
            runtime: inputArguments.runtime,
            status: terminalStatus,
            finishReason: terminalStatus === 'complete' ? optionalTrimmedString(inputArguments.session.assistantMessage.finishReason) : terminalStatus,
            notifyUser: false
        });
        inputArguments.markDone();
    };

    const synchronize = async (): Promise<void> => {
        const hydrationSession = inputArguments.hydrationSession();
        if (inputArguments.apiClient === null || hydrationSession === null || disposed || !inputArguments.hasSharedStreamState()) {
            return;
        }
        while (!disposed && inputArguments.session.active) {
            const hydrationResult = await hydrationSession.request(0);
            if (disposed) {
                return;
            }
            if (resolveHydratedTerminalStatus(inputArguments.session) !== null) {
                finalizeHydratedTerminalState();
                return;
            }
            const status = await fetchChatStreamStatusSnapshot(inputArguments.apiClient, inputArguments.session.conversationId);
            if (disposed) {
                return;
            }
            if (status.active) {
                if (!sessionMatchesActiveStatus(inputArguments.session, status)) {
                    finalizeChatStreamOwnerCancellation({
                        session: inputArguments.session,
                        runtime: inputArguments.runtime,
                        notifyUser: false
                    });
                    inputArguments.session.active = false;
                    inputArguments.releaseOwnerHandlers();
                    try {
                        if (inputArguments.syncActiveStatusAfterOwnerRelease !== null) {
                            await inputArguments.syncActiveStatusAfterOwnerRelease(inputArguments.session.conversationId);
                        }
                    } finally {
                        inputArguments.markDone();
                    }
                    return;
                }
                inputArguments.session.countsAsStreaming = true;
                inputArguments.runtime.notify(inputArguments.session, { type: 'replay' });
                if (hydrationResult.status === 'recoverable') {
                    continue;
                }
                return;
            }
            const terminalMessage = await waitForInactiveTerminalAssistantState({
                apiClient: inputArguments.apiClient,
                identity: {
                    conversationId: inputArguments.session.conversationId,
                    assistantTimestamp: inputArguments.session.assistantTimestamp,
                    assistantTurnTimestamp: inputArguments.session.assistantTurnTimestamp,
                    modelVariantIndex: inputArguments.session.modelVariantIndex
                },
                initialMessage: inputArguments.session.assistantMessage,
                shouldContinue: () => !disposed && inputArguments.session.active
            });
            if (disposed || !inputArguments.session.active) {
                return;
            }
            if (terminalMessage !== null) {
                applyAssistantMessageSnapshot(inputArguments.session, terminalMessage);
            }
            finalizeHydratedTerminalState();
            return;
        }
    };

    return {
        request: (): void => {
            if (syncPromise !== null || disposed) {
                return;
            }
            syncPromise = synchronize()
                .catch((error) => {
                    if (disposed) {
                        return;
                    }
                    const runtimeError = ensureError(error);
                    log('warn', 'Owner stream reconnect sync failed', { convId: inputArguments.session.conversationId, error: runtimeError });
                    inputArguments.failProtocol(`Chat stream reconnect sync failed: ${runtimeError.message}`, 'stream_hydration_failed');
                })
                .finally(() => {
                    syncPromise = null;
                });
        },
        dispose: (): void => {
            disposed = true;
            syncPromise = null;
        }
    };
};

export { createOwnerReconnectSync };
export type { OwnerReconnectSync };
