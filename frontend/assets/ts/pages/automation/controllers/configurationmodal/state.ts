/* SoAI - Automation configuration modal state [frontend/assets/ts/pages/automation/controllers/configurationmodal/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { buildAgentSettingsWithMaxIterations, readAgentMaxIterationsFromAgentSettings } from '@core/chat/parameters/agentMaxIterations.ts';
import { STORED_CHAT_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { cloneChatParameters, type ChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { buildStoredChatParameters } from '@core/chat/parameters/chatRequestParameters.ts';
import type { AutomationDefinition } from '@features/automation/public.ts';

type AutomationPromptSettings = {
    userSystemPrompt: string | null;
    userSystemPromptLockEnabled: boolean;
    soaiSystemPromptEnabled: boolean;
    additionalPrompts: Record<string, JsonValue>;
};

type AutomationParametersState = {
    parameters: ChatParameters;
    prompts: AutomationPromptSettings;
    hasExplicitParameters: boolean;
    hasExplicitPrompts: boolean;
};

const createDefaultAutomationParametersState = (): AutomationParametersState => {
    return {
        parameters: cloneChatParameters({}),
        prompts: {
            userSystemPrompt: null,
            userSystemPromptLockEnabled: false,
            soaiSystemPromptEnabled: true,
            additionalPrompts: {}
        },
        hasExplicitParameters: false,
        hasExplicitPrompts: false
    };
};

const resolveAutomationPromptSettings = (prompts: AutomationDefinition['modelSettings']['prompts'] | null): AutomationPromptSettings => {
    const promptSettings: AutomationPromptSettings = {
        userSystemPrompt: prompts?.userSystemPrompt ?? null,
        userSystemPromptLockEnabled: prompts?.userSystemPromptLockEnabled === true,
        soaiSystemPromptEnabled: prompts?.soaiSystemPromptEnabled ?? true,
        additionalPrompts: { ...prompts?.additionalPrompts }
    };
    return promptSettings;
};

const resolveAutomationParametersState = (modelSettings: AutomationDefinition['modelSettings']): AutomationParametersState => {
    const prompts = modelSettings.prompts ?? null;
    const parameters = cloneChatParameters(modelSettings);
    parameters.agentMaxIterations = readAgentMaxIterationsFromAgentSettings(modelSettings.agent);
    return {
        parameters,
        prompts: resolveAutomationPromptSettings(prompts),
        hasExplicitParameters: STORED_CHAT_PARAMETER_KEYS.some((key) => modelSettings[key] !== undefined) || modelSettings.agent.maxIterations !== undefined,
        hasExplicitPrompts: prompts !== null
    };
};

const applyAutomationParametersStateToModelSettings = (state: AutomationParametersState, settings: AutomationDefinition['modelSettings']): void => {
    if (state.hasExplicitParameters) {
        const requestParameters = buildStoredChatParameters(state.parameters);
        for (const key of STORED_CHAT_PARAMETER_KEYS) {
            delete settings[key];
        }
        Object.entries(requestParameters).forEach(([key, value]) => {
            settings[key] = value;
        });
        settings.agent = {
            ...buildAgentSettingsWithMaxIterations(state.parameters, settings.agent),
            mode: 'execute'
        };
    }
    if (state.hasExplicitPrompts) {
        settings.prompts = {
            userSystemPrompt: state.prompts.userSystemPrompt,
            userSystemPromptLockEnabled: state.prompts.userSystemPromptLockEnabled,
            soaiSystemPromptEnabled: state.prompts.soaiSystemPromptEnabled,
            additionalPrompts: { ...state.prompts.additionalPrompts }
        };
    }
};

export { applyAutomationParametersStateToModelSettings, createDefaultAutomationParametersState, resolveAutomationParametersState };
export type { AutomationParametersState };
