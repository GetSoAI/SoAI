/* SoAI - Chat stream service listener subscription replay [frontend/assets/ts/features/chat/chatstreamservice/serviceSubscription.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { isFunction } from '@core/typeGuards.ts';
import { buildUpdate } from '@features/chat/chatstreamservice/events.ts';
import type { ChatStreamSession, StreamListener } from '@features/chat/chatstreamservice/types.ts';

type ChatStreamSubscriptionNotificationQueue = {
    flushPending(): void;
    clearPending(): void;
};

const log = createModuleLogger('ChatStreamService', { defaultLevel: 'warn' });

const subscribeToChatStreamUpdates = (inputArguments: { listener: StreamListener; listeners: Set<StreamListener>; sessions: Map<string, ChatStreamSession>; notificationQueue: ChatStreamSubscriptionNotificationQueue }): (() => void) => {
    if (!isFunction(inputArguments.listener)) {
        throw new Error('Chat stream subscriber must be a function');
    }
    inputArguments.notificationQueue.flushPending();
    inputArguments.listeners.add(inputArguments.listener);
    for (const session of inputArguments.sessions.values()) {
        if (!session.active || session.status !== 'streaming') continue;
        try {
            const result = inputArguments.listener(buildUpdate(session));
            if (result !== undefined) {
                terminateHandledPromise(result.catch((error) => log('warn', 'Chat stream subscriber replay failed', ensureError(error))));
            }
        } catch (error) {
            log('warn', 'Chat stream subscriber replay failed', ensureError(error));
        }
    }
    return () => {
        inputArguments.listeners.delete(inputArguments.listener);
        if (!inputArguments.listeners.size) {
            inputArguments.notificationQueue.clearPending();
        }
    };
};

export { subscribeToChatStreamUpdates };
