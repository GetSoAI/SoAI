/* SoAI - Backend chat preference management [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/backendChatPreferencesManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { applyBackendChatPreferencesToPageState, buildBackendChatPreferencesPatch, isChatConversationSettingsWritable, type ChatPageApi } from '@features/chat/public.ts';
import { isConversationAuthorityLocked } from '@core/chat/conversationAuthorityLock.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import { requireStorageService } from '@core/storage/runtime.ts';
import { cloneChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';

interface BackendChatPreferencesHost extends ChatConversationStateHost, ChatSettingsStateHost, ChatConversationViewHost {
    api: ChatPageApi;
}

const cloneJsonObject = (value: JsonObject): JsonObject => {
    const result: JsonObject = {};
    for (const [key, entry] of Object.entries(value)) {
        result[key] = entry;
    }
    return result;
};

const loadBackendChatPreferences = async (host: BackendChatPreferencesHost): Promise<void> => {
    if (host.settings.backendPreferencesLoad) {
        await host.settings.backendPreferencesLoad;
        return;
    }
    const loadPromise = loadBackendChatPreferencesOnce(host).finally(() => {
        if (host.settings.backendPreferencesLoad === loadPromise) {
            host.settings.backendPreferencesLoad = null;
        }
    });
    host.settings.backendPreferencesLoad = loadPromise;
    await loadPromise;
};

const loadBackendChatPreferencesOnce = async (host: BackendChatPreferencesHost): Promise<void> => {
    const capturedModel = host.conversationState.currentModel;
    const capturedModelGeneration = host.conversationState.currentModelGeneration;
    const capturedParameters = cloneChatParameters(host.settings.parameters);
    const capturedParametersGeneration = host.settings.parametersGeneration;
    const storage = requireStorageService();
    let preferences: JsonObject;
    try {
        preferences = await storage.refreshAuthoritativeChatPreferences();
    } catch (error) {
        const pending = storage.getPendingConversationDefaults();
        if (host.settings.backendPreferences && Object.keys(pending).length > 0) {
            const applied = applyBackendChatPreferencesToPageState(host.settings.backendPreferences, capturedModel, capturedParameters, pending);
            host.conversationState.applyAuthoritativeCurrentModel(applied.currentModel, capturedModelGeneration);
            host.settings.applyAuthoritativeParameters(applied.parameters, capturedParametersGeneration);
        }
        throw error;
    }
    const nextPreferences = cloneJsonObject(preferences);
    const applied = applyBackendChatPreferencesToPageState(nextPreferences, capturedModel, capturedParameters, storage.getPendingConversationDefaults());
    host.conversationState.applyAuthoritativeCurrentModel(applied.currentModel, capturedModelGeneration);
    host.settings.applyAuthoritativeParameters(applied.parameters, capturedParametersGeneration);
};

const persistBackendChatPreferences = async (host: BackendChatPreferencesHost): Promise<void> => {
    if (host.settings.backendPreferencesLoad) {
        await host.settings.backendPreferencesLoad;
    }
    const currentConversation = host.conversationView.current();
    if (host.conversationState.currentConversationId !== null && currentConversation === null) throw new Error('Backend chat preference persistence requires the selected conversation to be loaded');
    if (isConversationAuthorityLocked(currentConversation)) return;
    if (isChatConversationSettingsWritable(currentConversation)) throw new Error('Backend chat preference persistence is only valid outside writable chat conversations');
    const nextPreferences = buildBackendChatPreferencesPatch(host.conversationState.currentModel, host.settings.parameters, host.settings.backendPreferences);
    if (Object.keys(nextPreferences).length === 0) return;
    await requireStorageService().persistAuthoritativeChatPatch(nextPreferences);
};

const persistBackendChatPreferencePatch = async (host: BackendChatPreferencesHost, patch: JsonObject): Promise<void> => {
    if (host.settings.backendPreferencesLoad) await host.settings.backendPreferencesLoad;
    await requireStorageService().persistAuthoritativeChatPatch(cloneJsonObject(patch));
};

export { loadBackendChatPreferences, persistBackendChatPreferencePatch, persistBackendChatPreferences };
