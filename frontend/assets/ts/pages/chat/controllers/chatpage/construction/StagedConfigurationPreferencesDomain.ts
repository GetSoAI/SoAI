/* SoAI - Staged chat configuration preference persistence [frontend/assets/ts/pages/chat/controllers/chatpage/construction/StagedConfigurationPreferencesDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildBackendChatPreferencesPatch, isChatConversationSettingsWritable, type ChatParameters } from '@features/chat/public.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { buildChatConfigurationPreferencePatch } from '@pages/chat/controllers/chatconfigurationcontroller/chatConfigurationPreferencePatchDomain.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { ChatPreferencesManager } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';

interface StagedConfigurationPreferencesHost extends ChatConfigurationRuntimeOwner, ChatConversationViewHost, ChatSettingsStateHost {
    preferences: Pick<ChatPreferencesManager, 'prepareConfigurationPatch'>;
}

const mergeObjects = (base: JsonObject, patch: JsonObject): JsonObject => {
    const merged: JsonObject = { ...base };
    for (const [key, value] of Object.entries(patch)) {
        const current = merged[key];
        merged[key] = isJsonObject(current) && isJsonObject(value) ? mergeObjects(current, value) : value;
    }
    return merged;
};

const persistStagedConfigurationPreferences = (host: StagedConfigurationPreferencesHost, parameters: ChatParameters, model: string | null, isPresentationActive: () => boolean): (() => Promise<void>) => {
    const configuration = host.configurationRuntime.requireConfiguration();
    const baseline = configuration.getParameterBaseline();
    if (!baseline) throw new Error('Staged chat preference baseline is unavailable.');
    const identityController = host.configurationRuntime.requireConversationSettings().presetControllers().identityPromptsController;
    const identity = identityController.workingSnapshot();
    const identityBaseline = identityController.baselineSnapshot();
    if (!identity || !identityBaseline) throw new Error('Staged identity preferences are unavailable.');
    const textZoomValue: JsonValue | undefined = parameters.textZoom;
    if (typeof textZoomValue !== 'number' || !Number.isFinite(textZoomValue)) throw new Error('Staged chat text zoom is invalid.');
    let patch = buildChatConfigurationPreferencePatch(parameters, baseline, textZoomValue, {
        current: { enabled: identity.userSystemPromptLockEnabled, value: identity.userSystemPrompt },
        baseline: { enabled: identityBaseline.userSystemPromptLockEnabled, value: identityBaseline.userSystemPrompt }
    });
    if (!isChatConversationSettingsWritable(host.conversationView.current())) patch = mergeObjects(buildBackendChatPreferencesPatch(model, parameters, host.settings.backendPreferences, { includeMcp: false }), patch);
    const persist = Object.keys(patch).length > 0 ? host.preferences.prepareConfigurationPatch(patch) : async (): Promise<void> => undefined;
    return async (): Promise<void> => {
        await persist();
        if (isPresentationActive()) identityController.finalizePreferenceSave();
    };
};

export { persistStagedConfigurationPreferences };
export type { StagedConfigurationPreferencesHost };
