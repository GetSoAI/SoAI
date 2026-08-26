/* SoAI - Chat feature persistence [frontend/assets/ts/features/chat/storage/persistence.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isBoolean } from '@core/typeGuards.ts';
import { buildPreferencesSnapshot } from '@features/chat/storage/state.ts';
import type { ChatStorageManagerContract } from '@features/chat/storage/managerContracts.ts';

type ChatPersistenceRuntime = Pick<ChatStorageManagerContract, 'getPreferencesSnapshot' | 'initialized' | 'isMobileSidebarViewport' | 'lastSerializedPreferences' | 'resolveStoredPreferences' | 'state' | 'storage'>;

function setIfBoolean(target: () => boolean | undefined, setter: (value: boolean) => void): void {
    const value = target();
    if (isBoolean(value)) {
        setter(value);
    }
}

const loadState = async (manager: ChatPersistenceRuntime): Promise<void> => {
    const storage = manager.storage;
    await storage.ready;

    manager.state.setConversations(new Map());
    manager.state.setCurrentConversationId(null);

    const storedPreferences = storage.getChatPreferences();
    const resolvedParameters = manager.resolveStoredPreferences(storedPreferences);
    manager.state.setParameters(resolvedParameters);
    setIfBoolean(() => storage.getChatSidebarOpen(), manager.state.setSidebarOpen);
    const persistedShowFavoritesAtTop = storage.getChatShowFavoritesAtTop();
    setIfBoolean(() => persistedShowFavoritesAtTop, manager.state.setShowFavoritesAtTop);

    const isMobile = manager.isMobileSidebarViewport();
    if (isMobile) {
        manager.state.setSidebarOpen(false);
    }

    manager.lastSerializedPreferences = JSON.stringify(manager.getPreferencesSnapshot());
    manager.initialized = true;
};

function saveChatState(manager: ChatPersistenceRuntime, _force = false): void {
    if (!manager.initialized) {
        return;
    }
    manager.storage.setChatSidebarOpen(manager.state.getSidebarOpen());
    manager.storage.setChatShowFavoritesAtTop(manager.state.getShowFavoritesAtTop());
}

function savePreferences(manager: ChatPersistenceRuntime, force = false): void {
    if (!manager.initialized) return;
    const preferences = buildPreferencesSnapshot(manager);
    const serialized = JSON.stringify(preferences);
    if (force || serialized !== manager.lastSerializedPreferences) {
        manager.lastSerializedPreferences = serialized;
        manager.storage.setChatPreferences(preferences);
    }
}

export { loadState, saveChatState, savePreferences };
