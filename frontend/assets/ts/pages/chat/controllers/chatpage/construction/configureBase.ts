/* SoAI - Chat page configure base [frontend/assets/ts/pages/chat/controllers/chatpage/construction/configureBase.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LogLevel } from '@core/moduleContext.ts';
import type { ChatUiStorage } from '@core/chat/protocols.ts';
import { TextZoomController } from '@core/TextZoomController.ts';
import { isBoolean, isNumber, isString } from '@core/typeGuards.ts';
import { isJsonValue, type JsonRecord, type JsonValue } from '@core/types/jsonValues.ts';
import type { ChatPageStorageSource, ChatTextZoomPageHost } from '@pages/chat/controllers/chatpage/construction/baseHost.ts';
import { serializeChatPreferences } from '@core/storage/persistence/chatPreferenceSerialization.ts';
import type { TimerHost } from '@pages/chat/controllers/chatUiBehaviors.ts';
import { ChatSettingsState } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';

interface ChatFoundationDependencies {
    storage: ChatPageStorageSource;
    pageDom: PageDom;
    pageResources: PageResources;
    getDocumentElement(): HTMLElement;
}

const createChatStorage = (storage: ChatPageStorageSource): ChatUiStorage => {
    const resolveBoolean = (value: JsonValue, contextMessage: string): boolean => {
        if (!isBoolean(value)) {
            throw new Error(contextMessage);
        }
        return value;
    };
    const resolveJsonStorageValue = (value: JsonValue | undefined, contextMessage: string): JsonValue => {
        if (!isJsonValue(value)) {
            throw new Error(contextMessage);
        }
        return value;
    };
    const sessionUsername = storage.session?.['username'];
    const session = isString(sessionUsername) && sessionUsername.trim() ? { username: sessionUsername } : null;
    const chatStorage: ChatUiStorage = {
        ready: storage.ready,
        getChatTextZoom: (defaultZoom: number) => {
            const value = storage.getChatTextZoom(defaultZoom);
            if (!isNumber(value) || !Number.isFinite(value)) {
                throw new Error('Chat storage returned an invalid text zoom value');
            }
            return value;
        },
        setChatTextZoom: (value: number) => storage.setChatTextZoom(value),
        getChatPreferences: () => resolveJsonStorageValue(serializeChatPreferences(storage.getChatPreferences()), 'Chat storage preferences payload must be JSON-compatible'),
        setChatPreferences: (preferences: JsonRecord) => storage.setChatPreferences(preferences),
        getChatWidescreenMode: () => resolveBoolean(storage.getChatWidescreenMode(), 'Chat storage returned an invalid widescreen mode value'),
        setChatWidescreenMode: (value: boolean) => storage.setChatWidescreenMode(value),
        getChatSidebarOpen: () => resolveBoolean(storage.getChatSidebarOpen(), 'Chat storage returned an invalid sidebar open value'),
        setChatSidebarOpen: (value: boolean) => storage.setChatSidebarOpen(value),
        getChatShowFavoritesAtTop: () => resolveBoolean(storage.getChatShowFavoritesAtTop(), 'Chat storage returned an invalid show-favorites-at-top value'),
        setChatShowFavoritesAtTop: (value: boolean) => storage.setChatShowFavoritesAtTop(value),
        getChatPlanBarVisible: () => resolveBoolean(storage.getChatPlanBarVisible(), 'Chat storage returned an invalid plan bar visibility value'),
        setChatPlanBarVisible: (value: boolean) => storage.setChatPlanBarVisible(value),
        getCodeRecognitionEnabled: () => resolveBoolean(storage.getCodeRecognitionEnabled(), 'Chat storage returned an invalid code recognition value'),
        getAssistantAvatar: () => storage.getAssistantAvatar(),
        setAssistantAvatar: (value: string | null) => storage.setAssistantAvatar(value),
        getUserAvatar: () => storage.getUserAvatar(),
        setUserAvatar: (value: string | null) => storage.setUserAvatar(value)
    };
    if (session) {
        chatStorage.session = session;
    }
    return chatStorage;
};

const createTextZoomPageHost = (page: ChatFoundationDependencies): ChatTextZoomPageHost => {
    return {
        dom: {
            getDocumentElement: (): HTMLElement => page.getDocumentElement()
        },
        pageDom: page.pageDom
    };
};

const createTimerHost = (page: ChatFoundationDependencies): TimerHost => {
    return {
        setTimer: (functionValue, delayMs, options) => {
            const timerId = page.pageResources.setTimer(functionValue, delayMs, options);
            if (timerId === null) {
                throw new Error('ChatPage failed to allocate timer');
            }
            return timerId;
        },
        clearTimer: (timerId) => page.pageResources.clearTimer(timerId)
    };
};

const createChatFoundation = (page: ChatFoundationDependencies, logger: (level: LogLevel, message: string, error?: Error) => void): { settings: ChatSettingsState; timers: TimerHost } => {
    const storage = createChatStorage(page.storage);
    const textZoomController = TextZoomController.createForChat(storage, (level, message, error): void => logger(level, message, error));
    const settings = new ChatSettingsState(storage, textZoomController, createTextZoomPageHost(page));
    return { settings, timers: createTimerHost(page) };
};

export { createChatFoundation };
export type { ChatFoundationDependencies };
