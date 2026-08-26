/* SoAI - Chat feature system prompt lock [frontend/assets/ts/features/chat/systemPromptLock.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isBoolean } from '@core/typeGuards.ts';
import type { ChatUiStorage } from '@core/chat/protocols.ts';
import type { ConversationModelSettings, ConversationPromptSettings } from '@core/chat/executionSettingsTypes.ts';

const USER_SYSTEM_PROMPT_LOCK_ENABLED_PREFERENCE_KEY = 'user_system_prompt_lock_enabled';
const USER_SYSTEM_PROMPT_LOCK_VALUE_PREFERENCE_KEY = 'user_system_prompt_lock_value';

type UserSystemPromptLockState = {
    enabled: boolean;
    value: string | null;
};

const readUserSystemPromptLockState = (chatPreferences: JsonValue): UserSystemPromptLockState => {
    const preferences = isJsonObject(chatPreferences) ? chatPreferences : null;
    const enabledValue = preferences ? preferences[USER_SYSTEM_PROMPT_LOCK_ENABLED_PREFERENCE_KEY] : undefined;
    const lockValue = preferences ? preferences[USER_SYSTEM_PROMPT_LOCK_VALUE_PREFERENCE_KEY] : undefined;
    return {
        enabled: isBoolean(enabledValue) ? enabledValue : false,
        value: toTrimmedStringOrNull(lockValue)
    };
};

const writeUserSystemPromptLockState = (storage: ChatUiStorage, state: UserSystemPromptLockState): void => {
    const patch: JsonObject = {};
    patch[USER_SYSTEM_PROMPT_LOCK_ENABLED_PREFERENCE_KEY] = state.enabled;
    patch[USER_SYSTEM_PROMPT_LOCK_VALUE_PREFERENCE_KEY] = state.value;
    storage.setChatPreferences(patch);
};

const resolveConversationUserSystemPrompt = (modelSettings: ConversationModelSettings): string | null => {
    return toTrimmedStringOrNull(modelSettings.prompts?.userSystemPrompt);
};

const applyUserSystemPromptToModelSettings = (modelSettings: ConversationModelSettings, prompt: string | null): { next: ConversationModelSettings; changed: boolean } => {
    const normalizedPrompt = toTrimmedStringOrNull(prompt);
    const current = resolveConversationUserSystemPrompt(modelSettings);
    const changed = current !== normalizedPrompt;
    if (!changed) {
        return { next: modelSettings, changed: false };
    }

    const prompts = modelSettings.prompts;
    const nextPrompts: ConversationPromptSettings = {
        userSystemPrompt: normalizedPrompt,
        soaiSystemPromptEnabled: prompts?.soaiSystemPromptEnabled ?? true,
        additionalSettings: { ...prompts?.additionalSettings }
    };
    if (prompts?.userSystemPromptLockEnabled !== undefined) nextPrompts.userSystemPromptLockEnabled = prompts.userSystemPromptLockEnabled;
    return {
        next: { ...modelSettings, prompts: nextPrompts },
        changed: true
    };
};

export { applyUserSystemPromptToModelSettings, readUserSystemPromptLockState, writeUserSystemPromptLockState };
export type { UserSystemPromptLockState };
