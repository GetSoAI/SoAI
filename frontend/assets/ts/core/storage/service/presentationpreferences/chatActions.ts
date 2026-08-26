/* SoAI - Chat presentation preference mutations [frontend/assets/ts/core/storage/service/presentationpreferences/chatActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';

interface ChatPresentationPreferenceActions {
    setChatWidescreenMode(enabled: boolean): void;
    setChatSidebarOpen(open: boolean): void;
    setChatShowFavoritesAtTop(enabled: boolean): void;
    setChatPlanBarVisible(visible: boolean): void;
    setAssistantAvatar(value: string | null): void;
    setUserAvatar(value: string | null): void;
}

const createChatPresentationPreferenceActions = (core: StorageRuntime): ChatPresentationPreferenceActions => {
    const state = core.state;
    const setChatWidescreenMode = (enabled: boolean): void => {
        if (state.cache.chat.widescreenMode !== !!enabled) {
            state.cache.chat.widescreenMode = !!enabled;
            terminateHandledPromise(core.queuePersist('chat'));
        }
    };
    const setChatSidebarOpen = (open: boolean): void => {
        if (state.cache.chat.sidebarOpen !== !!open) {
            state.cache.chat.sidebarOpen = !!open;
            terminateHandledPromise(core.queuePersist('chat'));
        }
    };
    const setChatShowFavoritesAtTop = (enabled: boolean): void => {
        if (state.cache.chat.showFavoritesAtTop !== !!enabled) {
            state.cache.chat.showFavoritesAtTop = !!enabled;
            terminateHandledPromise(core.queuePersist('chat'));
        }
    };
    const setChatPlanBarVisible = (visible: boolean): void => {
        if (state.cache.chat.planBarVisible !== !!visible) {
            state.cache.chat.planBarVisible = !!visible;
            terminateHandledPromise(core.queuePersist('chat'));
        }
    };
    const setAssistantAvatar = (value: string | null): void => {
        state.cache.chat.assistantAvatar = value || null;
        terminateHandledPromise(core.queuePersist('chat'));
    };
    const setUserAvatar = (value: string | null): void => {
        state.cache.chat.userAvatar = value || null;
        terminateHandledPromise(core.queuePersist('chat'));
    };
    return { setChatWidescreenMode, setChatSidebarOpen, setChatShowFavoritesAtTop, setChatPlanBarVisible, setAssistantAvatar, setUserAvatar };
};

export { createChatPresentationPreferenceActions };
