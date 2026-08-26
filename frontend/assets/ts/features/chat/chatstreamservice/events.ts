/* SoAI - Chat feature stream service events [frontend/assets/ts/features/chat/chatstreamservice/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModuleLogger, resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { showUserError, showUserSuccess, showUserWarning } from '@core/ui/notifications/notifications.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { resolveChatRequestErrorNotificationMessage } from '@features/chat/chatErrorPresentation.ts';
import type { ChatNotifyPrefs, ChatStreamSession, StreamListener, StreamMutationType, StreamUpdate } from '@features/chat/chatstreamservice/types.ts';

const log = createModuleLogger('ChatStreamService', { defaultLevel: 'warn' });

type ChatNotificationPreferencesSource = { parameters: Partial<Record<keyof ChatNotifyPrefs, boolean>> };

const isChatStorageService = <T>(value: T): value is T & { getChatPreferences: () => ChatNotificationPreferencesSource } => isObject(value) && hasFunctionProperty(value, 'getChatPreferences');

const getChatStorageService = (): { getChatPreferences: () => ChatNotificationPreferencesSource } => {
    const candidate = resolveKernelService('core.storage');
    if (!isChatStorageService(candidate)) {
        throw new Error('Chat stream service requires core.storage.getChatPreferences()');
    }
    return candidate;
};

const readStoragePreferences = (): ChatNotificationPreferencesSource => {
    return getChatStorageService().getChatPreferences();
};

const getNotifyPrefs = (): ChatNotifyPrefs => {
    const defaults: ChatNotifyPrefs = { notifyOnCompletion: false, notifyOnError: true };
    const parameters = readStoragePreferences().parameters;

    const resolveBool = (key: keyof ChatNotifyPrefs): boolean => {
        if (typeof parameters[key] === 'boolean') {
            return parameters[key];
        }
        return defaults[key];
    };

    return {
        notifyOnCompletion: resolveBool('notifyOnCompletion'),
        notifyOnError: resolveBool('notifyOnError')
    };
};

const buildTerminalUserNotifier = (session: ChatStreamSession, title: string | null): (() => void) | null => {
    const prefs = getNotifyPrefs();

    if (session.status === 'complete') {
        if (!prefs.notifyOnCompletion) {
            return null;
        }
        const message = title ? i18n.t('chat.notifications.requestComplete', { title }) : i18n.t('chat.notifications.requestCompleteGeneric');
        return (): void => {
            showUserSuccess(message);
        };
    }

    if (session.status === 'error') {
        if (!prefs.notifyOnError) {
            return null;
        }
        const message = resolveChatRequestErrorNotificationMessage({ error: session.lastError, title });
        return (): void => {
            showUserError(message);
        };
    }

    if (session.status === 'cancelled') {
        if (!prefs.notifyOnError) {
            return null;
        }
        const message = i18n.t('chat.notifications.requestCancelled');
        return (): void => {
            showUserWarning(message);
        };
    }

    return null;
};

const buildUpdate = (session: ChatStreamSession, mutation?: { type: StreamMutationType; textDelta?: string | null }): StreamUpdate => {
    return {
        conversationId: session.conversationId,
        assistantTimestamp: session.assistantTimestamp,
        assistantTurnTimestamp: session.assistantTurnTimestamp,
        status: session.status,
        countsAsStreaming: session.countsAsStreaming,
        message: session.assistantMessage,
        assistantRevision: session.assistantRevision,
        modelVariantIndex: session.modelVariantIndex,
        requestId: session.requestId,
        usagePreview: session.usagePreview,
        mutation: {
            type: mutation?.type ?? 'replay',
            textDelta: typeof mutation?.textDelta === 'string' && mutation.textDelta.length > 0 ? mutation.textDelta : null
        }
    };
};

const notifyListeners = (listeners: Set<StreamListener>, session: ChatStreamSession, mutation?: { type: StreamMutationType; textDelta?: string | null }): void => {
    if (!listeners.size) {
        return;
    }
    const update = buildUpdate(session, mutation);
    for (const listener of listeners) {
        try {
            const result = listener(update);
            if (result !== undefined) {
                terminateHandledPromise(result.catch((error) => log('warn', 'Chat stream subscriber update failed', ensureError(error))));
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            log('warn', 'Chat stream subscriber update failed', runtimeError);
        }
    }
};

const notifyListenersAndWait = async (listeners: Set<StreamListener>, session: ChatStreamSession, mutation: { type: StreamMutationType; textDelta?: string | null }): Promise<void> => {
    if (!listeners.size) {
        return;
    }
    const update = buildUpdate(session, mutation);
    await Promise.all(
        Array.from(listeners, async (listener): Promise<void> => {
            try {
                await listener(update);
            } catch (error) {
                log('warn', 'Chat stream subscriber checkpoint failed', ensureError(error));
            }
        })
    );
};

export { buildTerminalUserNotifier, buildUpdate, notifyListeners, notifyListenersAndWait };
