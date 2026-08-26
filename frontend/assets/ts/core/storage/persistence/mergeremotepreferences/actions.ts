/* SoAI - Shared storage merge remote preferences actions [frontend/assets/ts/core/storage/persistence/mergeremotepreferences/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeStringArray } from '@core/storage/normalization.ts';
import type { ChatCache, ChatPreferencesManager } from '@core/storage/persistence/mergeremotepreferences/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isBoolean, isNumber, isObject, isString } from '@core/typeGuards.ts';
import { CHAT_WIRE_TO_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';

const applyChatRequestParametersPatch = (patch: JsonValue | undefined, target: ChatPreferencesManager['parameters'], base: ChatPreferencesManager['parameters']): void => {
    if (!isObject(patch)) {
        return;
    }

    for (const [key, value] of Object.entries(patch)) {
        const parameterKey = CHAT_WIRE_TO_PARAMETER_KEYS[key] ?? key;
        if (!(parameterKey in base)) {
            continue;
        }

        if (parameterKey === 'stop') {
            target['stop'] = normalizeStringArray(value, 50);
            continue;
        }

        if (parameterKey === 'topLogprobs') {
            if (value === null || value === undefined) {
                target.topLogprobs = null;
                continue;
            }
            if (isNumber(value) && Number.isFinite(value)) {
                target.topLogprobs = value;
            }
            continue;
        }

        if (isBoolean(value) || isNumber(value) || isString(value) || value === null) {
            target[parameterKey] = value;
        }
    }
};

const applyChatPreferencesPatch = (patch: JsonValue | undefined, target: ChatPreferencesManager, base: ChatPreferencesManager): void => {
    if (!isObject(patch)) {
        return;
    }

    const hideRealModel = patch['hide_real_model'];
    if (isBoolean(hideRealModel)) {
        target.hideRealModel = hideRealModel;
    }

    const userSystemPromptLockEnabled = patch['user_system_prompt_lock_enabled'];
    if (isBoolean(userSystemPromptLockEnabled)) {
        target.userSystemPromptLockEnabled = userSystemPromptLockEnabled;
    }

    const userSystemPromptLockValue = patch['user_system_prompt_lock_value'];
    if (userSystemPromptLockValue === null || userSystemPromptLockValue === undefined || isString(userSystemPromptLockValue)) {
        target.userSystemPromptLockValue = userSystemPromptLockValue ?? null;
    }

    const parametersPatch = patch['parameters'];
    const mergedParameters = { ...base.parameters };
    applyChatRequestParametersPatch(parametersPatch, mergedParameters, base.parameters);
    target.parameters = mergedParameters;
};

const applyChatPatch = (patch: JsonValue | undefined, target: ChatCache, base: ChatCache): void => {
    if (!isObject(patch)) {
        return;
    }

    applyChatPreferencesPatch(patch['preferences'], target.preferences, base.preferences);

    const defaultEmbeddingModel = patch['default_embedding_model'];
    if (defaultEmbeddingModel === null || defaultEmbeddingModel === undefined || isString(defaultEmbeddingModel)) {
        target.defaultEmbeddingModel = defaultEmbeddingModel ?? null;
    }

    const textZoom = patch['text_zoom'];
    if (isNumber(textZoom) && Number.isFinite(textZoom)) {
        target.textZoom = textZoom;
    }

    const widescreenMode = patch['widescreen_mode'];
    if (isBoolean(widescreenMode)) {
        target.widescreenMode = widescreenMode;
    }

    const sidebarOpen = patch['sidebar_open'];
    if (isBoolean(sidebarOpen)) {
        target.sidebarOpen = sidebarOpen;
    }

    const showFavoritesAtTop = patch['show_favorites_at_top'];
    if (isBoolean(showFavoritesAtTop)) {
        target.showFavoritesAtTop = showFavoritesAtTop;
    }

    const planBarVisible = patch['plan_bar_visible'];
    if (isBoolean(planBarVisible)) {
        target.planBarVisible = planBarVisible;
    }

    const userAvatar = patch['user_avatar'];
    if (userAvatar === null || userAvatar === undefined || isString(userAvatar)) {
        target.userAvatar = userAvatar ?? null;
    }

    const assistantAvatar = patch['assistant_avatar'];
    if (assistantAvatar === null || assistantAvatar === undefined || isString(assistantAvatar)) {
        target.assistantAvatar = assistantAvatar ?? null;
    }
};

export { applyChatPatch, applyChatPreferencesPatch };
