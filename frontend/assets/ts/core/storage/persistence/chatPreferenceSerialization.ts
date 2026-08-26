/* SoAI - Frontend chat preference persistence serialization [frontend/assets/ts/core/storage/persistence/chatPreferenceSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatCache, ChatPreferencesManager } from '@core/storage/types.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { buildChatPreferencesPayload } from '@core/chat/parameters/chatParameterDefaults.ts';

const serializeChatPreferences = (preferences: ChatPreferencesManager): JsonObject => {
    const serializedParameters = buildChatPreferencesPayload({ parameters: preferences.parameters });
    return {
        parameters: serializedParameters.parameters,
        'hide_real_model': preferences.hideRealModel,
        'user_system_prompt_lock_enabled': preferences.userSystemPromptLockEnabled,
        'user_system_prompt_lock_value': preferences.userSystemPromptLockValue
    };
};

const serializeChatCache = (cache: ChatCache): JsonObject => {
    const serialized: JsonObject = {
        preferences: serializeChatPreferences(cache.preferences),
        'text_zoom': cache.textZoom,
        'widescreen_mode': cache.widescreenMode,
        'sidebar_open': cache.sidebarOpen,
        'show_favorites_at_top': cache.showFavoritesAtTop,
        'plan_bar_visible': cache.planBarVisible,
        'assistant_avatar': cache.assistantAvatar,
        'user_avatar': cache.userAvatar
    };
    if (cache.defaultEmbeddingModel !== undefined) {
        serialized['default_embedding_model'] = cache.defaultEmbeddingModel;
    }
    return serialized;
};

export { serializeChatCache, serializeChatPreferences };
