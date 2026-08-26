/* SoAI - Active chat stream status reconciliation loop lifecycle [frontend/assets/ts/features/chat/chatstreamservice/activeStatusReconciliationLoop.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { startPollingLoop, type PollingLoopHandle } from '@core/concurrency/pollingLoop.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import type { ChatStreamActiveStatusSyncRunner } from '@features/chat/chatstreamservice/activeStatusSyncRunner.ts';
import type { ActiveStatusInactiveTransitionArguments } from '@features/chat/chatstreamservice/activeStatusInactiveTransition.ts';

const ACTIVE_STATUS_RECONCILE_INTERVAL_MS = 5000;

type ActiveStatusReconciliationLoop = {
    sync(): void;
    stop(reason: string): void;
};

type ActiveStatusReconciliationLoopArguments = {
    sessions: Map<string, ChatStreamSession>;
    activeStatusSyncRunner: ChatStreamActiveStatusSyncRunner;
    syncGeneration(): number;
    selectedConversationId(): string | null;
    followerSessions: ActiveStatusInactiveTransitionArguments['followerSessions'];
    isActive(): boolean;
    isSyncCurrent(generation: number): boolean;
    logWarning(message: string, error: Error): void;
};

const hasActiveStreamingSession = (sessions: Map<string, ChatStreamSession>, conversationId: string | null): boolean => {
    if (conversationId === null) return false;
    const session = sessions.get(conversationId);
    return session?.active === true && session.status === 'streaming' && session.countsAsStreaming;
};

const createActiveStatusReconciliationLoop = (inputArguments: ActiveStatusReconciliationLoopArguments): ActiveStatusReconciliationLoop => {
    let statusReconcileLoop: PollingLoopHandle | null = null;

    const stop = (reason: string): void => {
        statusReconcileLoop?.stop(reason);
        statusReconcileLoop = null;
    };

    const start = (): void => {
        if (statusReconcileLoop !== null) {
            return;
        }
        statusReconcileLoop = startPollingLoop({
            label: 'chat-stream-active-status-reconciliation',
            initialDelayMs: ACTIVE_STATUS_RECONCILE_INTERVAL_MS,
            intervalMs: ACTIVE_STATUS_RECONCILE_INTERVAL_MS,
            run: async (): Promise<'stop' | void> => {
                const conversationId = inputArguments.selectedConversationId();
                if (conversationId === null || !hasActiveStreamingSession(inputArguments.sessions, conversationId)) {
                    return 'stop';
                }
                const bridgeGeneration = inputArguments.syncGeneration();
                await inputArguments.activeStatusSyncRunner.syncConversation({
                    conversationId,
                    context: 'presentation',
                    generation: bridgeGeneration,
                    followerSessions: inputArguments.followerSessions,
                    isCurrent: (generation: number): boolean => generation === bridgeGeneration && inputArguments.isSyncCurrent(generation)
                });
                if (!hasActiveStreamingSession(inputArguments.sessions, inputArguments.selectedConversationId())) {
                    statusReconcileLoop = null;
                    return 'stop';
                }
            },
            onError: (error): 'continue' => {
                inputArguments.logWarning('Active stream status reconciliation failed', ensureError(error));
                return 'continue';
            }
        });
    };

    const sync = (): void => {
        if (!inputArguments.isActive()) {
            stop('chat-stream-websocket-bridge-inactive');
            return;
        }
        if (hasActiveStreamingSession(inputArguments.sessions, inputArguments.selectedConversationId())) {
            start();
            return;
        }
        stop('chat-stream-websocket-bridge-idle');
    };

    return { sync, stop };
};

export { createActiveStatusReconciliationLoop };
export type { ActiveStatusReconciliationLoop };
