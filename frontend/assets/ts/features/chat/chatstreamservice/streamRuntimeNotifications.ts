/* SoAI - Chat stream runtime notification policy [frontend/assets/ts/features/chat/chatstreamservice/streamRuntimeNotifications.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPageTerminating } from '@core/lifecycle/pageTermination.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamTerminalNotificationCoordinator } from '@features/chat/chatstreamservice/terminalNotificationCoordinator.ts';
import { buildTerminalUserNotifier } from '@features/chat/chatstreamservice/events.ts';
import type { ChatStreamConversationTitleResolution } from '@features/chat/chatstreamservice/conversationTitleResolution.ts';
import type { StreamRequestDispositionRegistry } from '@features/chat/chatstreamservice/streamRequestDispositionRegistry.ts';
import type { ChatStreamNotificationQueue } from '@features/chat/chatstreamservice/streamNotificationQueue.ts';

type ChatStreamRuntimeAdmissionState = {
    markStreaming(session: { conversationId: string; requestId: string; assistantTimestamp: number; assistantTurnTimestamp: number; modelVariantIndex: number }): void;
    markTerminalizing(session: { conversationId: string; requestId: string; assistantTimestamp: number; assistantTurnTimestamp: number; modelVariantIndex: number }): void;
};

type ChatStreamRuntimeNotificationDependencies = {
    requestDispositions: StreamRequestDispositionRegistry;
    notificationQueue: ChatStreamNotificationQueue;
    conversationTitles: ChatStreamConversationTitleResolution;
    admissionState: ChatStreamRuntimeAdmissionState;
    terminalNotifications: ChatStreamTerminalNotificationCoordinator;
};

const createChatStreamRuntime = (inputArguments: ChatStreamRuntimeNotificationDependencies): StreamRuntime => ({
    notify: (session, mutation) => {
        if (inputArguments.requestDispositions.isRequestSuppressed(session.conversationId, session.requestId)) {
            return;
        }
        if (mutation?.type === 'terminal' || session.status !== 'streaming') {
            inputArguments.admissionState.markTerminalizing(session);
        } else if (session.countsAsStreaming === true) {
            inputArguments.admissionState.markStreaming(session);
        }
        inputArguments.notificationQueue.notify(session, mutation);
    },
    notifyCheckpoint: async (session, mutation) => {
        if (inputArguments.requestDispositions.isRequestSuppressed(session.conversationId, session.requestId)) return;
        inputArguments.admissionState.markStreaming(session);
        await inputArguments.notificationQueue.notifyCheckpoint(session, mutation);
    },
    notifyUser: (session) => {
        if (isPageTerminating()) {
            return;
        }
        if (inputArguments.requestDispositions.isRequestSuppressed(session.conversationId, session.requestId)) {
            return;
        }
        const title = inputArguments.conversationTitles.resolve(session);
        const terminalNotifier = buildTerminalUserNotifier(session, title);
        if (terminalNotifier === null) {
            return;
        }
        inputArguments.terminalNotifications.scheduleTerminalNotification({
            conversationId: session.conversationId,
            requestId: session.requestId,
            emit: terminalNotifier
        });
    }
});

export { createChatStreamRuntime };
