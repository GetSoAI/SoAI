/* SoAI - Chat stream run session lifecycle binding [frontend/assets/ts/features/chat/chatstreamservice/streamRunSessionLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { registerAbortListener } from '@features/chat/abort/abortSignalListener.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { createOwnerReconnectSync, type OwnerReconnectSync } from '@features/chat/chatstreamservice/ownerReconnectSync.ts';
import type { ChatStreamHydrationSession } from '@features/chat/chatstreamservice/streamHydrationSession.ts';
import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import type { ChatStreamCommandErrorEnvelope } from '@core/realtime/eventcontracts/chatStreamCommandError.ts';
import type { ChatStreamSession, HydratedSnapshotApplicationResult } from '@features/chat/chatstreamservice/types.ts';

type FailProtocol = (message: string, errorCode?: string | null, errorPayload?: JsonValue | null) => void;
type RegisterOwnerHandlers = (inputArguments: { conversationId: string; requestId: string; handleStreamEvent: (envelope: ChatStreamEventEnvelope) => void; handleCommandErrorEvent: (envelope: ChatStreamCommandErrorEnvelope) => void; applyHydratedSnapshot: (message: ChatMessage, notifyUserOnTerminal: boolean) => Promise<HydratedSnapshotApplicationResult> }) => () => void;

interface OwnerStreamSessionLifecycle {
    cleanup(): void;
    reconcile(): void;
}

type OwnerStreamSessionLifecycleArguments = {
    apiClient: ChatStreamApiClient | null;
    session: ChatStreamSession;
    runtime: StreamRuntime;
    registerOwnerHandlers: RegisterOwnerHandlers;
    handleStreamEvent: (envelope: ChatStreamEventEnvelope) => void;
    handleCommandErrorEvent: (envelope: ChatStreamCommandErrorEnvelope) => void;
    applyHydratedSnapshot: (message: ChatMessage, notifyUserOnTerminal: boolean) => Promise<HydratedSnapshotApplicationResult>;
    hydrationSession: () => ChatStreamHydrationSession | null;
    hasSharedStreamState: () => boolean;
    failProtocol: FailProtocol;
    markDone: () => void;
    handleAbort: () => void;
    handleDisconnected: () => void;
    syncActiveStatusAfterOwnerRelease: ((conversationId: string) => Promise<void>) | null;
};

const log = createModuleLogger('ChatStreamService', { defaultLevel: 'warn' });

const bindOwnerStreamSessionLifecycle = (inputArguments: OwnerStreamSessionLifecycleArguments): OwnerStreamSessionLifecycle => {
    let unsubscribeWsDisconnected: (() => void) | null = null;
    let unsubscribeWsConnected: (() => void) | null = null;
    let unregisterAbortListener: (() => void) | null = null;
    let unregisterOwnerHandlers: (() => void) | null = null;
    let ownerReconnectSync: OwnerReconnectSync | null = null;
    let ownerHandlersReleased = false;
    let cleaned = false;
    const handleCleanupError = (runtimeError: Error): void => {
        log('warn', 'Chat stream owner lifecycle cleanup failed', runtimeError);
    };
    const releaseOwnerHandlers = (): void => {
        if (ownerHandlersReleased) {
            return;
        }
        ownerHandlersReleased = true;
        runCleanup(unregisterOwnerHandlers, handleCleanupError);
        unregisterOwnerHandlers = null;
    };
    const cleanup = (): void => {
        if (cleaned) {
            return;
        }
        cleaned = true;
        runCleanup(unregisterAbortListener, handleCleanupError);
        unregisterAbortListener = null;
        runCleanup(unsubscribeWsDisconnected, handleCleanupError);
        unsubscribeWsDisconnected = null;
        runCleanup(unsubscribeWsConnected, handleCleanupError);
        unsubscribeWsConnected = null;
        releaseOwnerHandlers();
        ownerReconnectSync?.dispose();
        ownerReconnectSync = null;
    };
    try {
        unregisterOwnerHandlers = inputArguments.registerOwnerHandlers({
            conversationId: inputArguments.session.conversationId,
            requestId: inputArguments.session.requestId,
            handleStreamEvent: inputArguments.handleStreamEvent,
            handleCommandErrorEvent: inputArguments.handleCommandErrorEvent,
            applyHydratedSnapshot: inputArguments.applyHydratedSnapshot
        });
        ownerReconnectSync = createOwnerReconnectSync({
            apiClient: inputArguments.apiClient,
            hydrationSession: inputArguments.hydrationSession,
            session: inputArguments.session,
            runtime: inputArguments.runtime,
            hasSharedStreamState: inputArguments.hasSharedStreamState,
            failProtocol: inputArguments.failProtocol,
            markDone: inputArguments.markDone,
            releaseOwnerHandlers,
            syncActiveStatusAfterOwnerRelease: inputArguments.syncActiveStatusAfterOwnerRelease
        });
        unsubscribeWsDisconnected = subscribeManagedWebSocketContract({
            label: 'ChatStreamService',
            contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected,
            handler: inputArguments.handleDisconnected
        });
        unsubscribeWsConnected = subscribeManagedWebSocketContract({
            label: 'ChatStreamService',
            contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
            handler: () => ownerReconnectSync?.request()
        });
        unregisterAbortListener = registerAbortListener(inputArguments.session.abortController.signal, inputArguments.handleAbort);
        return { cleanup, reconcile: (): void => ownerReconnectSync?.request() };
    } catch (error) {
        cleanup();
        throw error;
    }
};

export { bindOwnerStreamSessionLifecycle };
export type { OwnerStreamSessionLifecycle };
