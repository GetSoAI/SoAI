/* SoAI - Backend-managed chat preferences [frontend/assets/ts/features/chat/backendChatPreferences.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { ChatParameters } from '@core/chat/parameters/types.ts';
import { applyAgentMaxIterationsParameterFromModelSettings, buildAgentSettingsWithMaxIterations } from '@core/chat/parameters/agentMaxIterations.ts';
import { CHAT_PARAMETER_WIRE_KEYS, STORED_CHAT_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { mergeConversationDefaultDelta } from '@core/chat/conversationDefaultPreferences.ts';
import type { RagConfigResponse } from '@core/api/contracts/webuiRagContracts.ts';
import type { McpConfig } from '@features/chat/conversationsettings/settingsModels.ts';

const AUTO_TITLE_GENERATION_KEY = 'auto_title_generation';
const CONVERSATION_DEFAULTS_VERSION = 1;

const cloneParameterValue = (value: JsonValue | undefined): JsonValue | undefined => {
    if (!isJsonValue(value)) {
        return undefined;
    }
    if (Array.isArray(value)) {
        return [...value];
    }
    return value;
};

const sparseDifference = (confirmed: JsonObject, desired: JsonObject): JsonObject => {
    const difference: JsonObject = {};
    for (const [key, desiredValue] of Object.entries(desired)) {
        const confirmedValue = confirmed[key];
        if (isJsonObject(desiredValue) && isJsonObject(confirmedValue)) {
            const nested = sparseDifference(confirmedValue, desiredValue);
            if (Object.keys(nested).length > 0) difference[key] = nested;
        } else if (JSON.stringify(confirmedValue) !== JSON.stringify(desiredValue)) {
            difference[key] = Array.isArray(desiredValue) ? [...desiredValue] : desiredValue;
        }
    }
    return difference;
};

const readBackendChatRecord = (preferences: JsonValue): JsonObject => {
    if (!isJsonObject(preferences)) {
        return {};
    }
    const chatValue = preferences['chat'];
    return isJsonObject(chatValue) ? chatValue : {};
};

const readBackendChatParametersRecord = (preferences: JsonValue): JsonObject => {
    const chatRecord = readBackendChatRecord(preferences);
    const chatPreferencesValue = chatRecord['preferences'];
    const chatPreferencesRecord = isJsonObject(chatPreferencesValue) ? chatPreferencesValue : {};
    const parametersValue = chatPreferencesRecord['parameters'];
    return isJsonObject(parametersValue) ? parametersValue : {};
};

const readBackendConversationDefaultsRecord = (preferences: JsonValue): JsonObject => {
    const chatRecord = readBackendChatRecord(preferences);
    const defaultsValue = chatRecord['conversation_defaults_v1'];
    if (!isJsonObject(defaultsValue)) {
        return {};
    }
    return defaultsValue['version'] === CONVERSATION_DEFAULTS_VERSION ? defaultsValue : {};
};

const readBackendConversationDefaultsModelSettings = (preferences: JsonValue): JsonObject => {
    const defaultsRecord = readBackendConversationDefaultsRecord(preferences);
    const modelSettingsValue = defaultsRecord['model_settings'];
    return isJsonObject(modelSettingsValue) ? modelSettingsValue : {};
};

const readBackendConversationDefaultsParameters = (preferences: JsonValue): JsonObject => {
    const modelSettings = readBackendConversationDefaultsModelSettings(preferences);
    const parametersValue = modelSettings['parameters'];
    return isJsonObject(parametersValue) ? parametersValue : {};
};

const readBackendConversationDefaultsMcp = (preferences: JsonValue): JsonObject => {
    const modelSettings = readBackendConversationDefaultsModelSettings(preferences);
    const mcpValue = modelSettings['mcp'];
    return isJsonObject(mcpValue) ? mcpValue : {};
};

type BackendCurrentModel = Readonly<{ present: false }> | Readonly<{ present: true; value: string | null }>;

const readBackendCurrentModel = (preferences: JsonValue): BackendCurrentModel => {
    const modelSettings = readBackendConversationDefaultsModelSettings(preferences);
    if (!('model' in modelSettings)) return { present: false };
    const modelValue = modelSettings['model'];
    if (modelValue === null) return { present: true, value: null };
    const model = optionalTrimmedString(modelValue);
    return model ? { present: true, value: model } : { present: false };
};

const readBackendToolsEnabled = (preferences: JsonValue): boolean | null => {
    const mcpRecord = readBackendConversationDefaultsMcp(preferences);
    const value = mcpRecord['tools_enabled'];
    return typeof value === 'boolean' ? value : null;
};

const readBackendToolApprovalRequired = (preferences: JsonValue): boolean | null => {
    const mcpRecord = readBackendConversationDefaultsMcp(preferences);
    const value = mcpRecord['tool_approval_required'];
    return typeof value === 'boolean' ? value : null;
};

const readBackendNewConversationInheritLastSettings = (preferences: JsonValue): boolean => {
    const parametersRecord = readBackendChatParametersRecord(preferences);
    const value = parametersRecord['new_conversation_inherit_last_settings'];
    return typeof value === 'boolean' ? value : true;
};

const readBackendAutoTitleGeneration = (preferences: JsonValue): boolean => {
    const parametersRecord = readBackendChatParametersRecord(preferences);
    const value = parametersRecord[AUTO_TITLE_GENERATION_KEY];
    return typeof value === 'boolean' ? value : true;
};

const applyBackendChatPreferencesToPageState = (preferences: JsonValue, currentModel: string | null, parameters: ChatParameters, pendingDefaults: JsonObject = {}): { currentModel: string | null; parameters: ChatParameters } => {
    const effectivePreferences = Object.keys(pendingDefaults).length > 0 ? overlayConversationDefaultDelta(preferences, pendingDefaults) : preferences;
    const nextParameters: ChatParameters = { ...parameters };
    const backendParameters = readBackendConversationDefaultsParameters(effectivePreferences);
    for (const key of STORED_CHAT_PARAMETER_KEYS) {
        const wireKey = CHAT_PARAMETER_WIRE_KEYS[key] ?? key;
        if (!(wireKey in backendParameters)) {
            continue;
        }
        const clonedValue = cloneParameterValue(backendParameters[wireKey]);
        if (clonedValue !== undefined) {
            nextParameters[key] = clonedValue;
        }
    }
    const toolsEnabled = readBackendToolsEnabled(effectivePreferences);
    if (toolsEnabled === true || toolsEnabled === false) {
        nextParameters.toolsEnabled = toolsEnabled;
    }
    const toolApprovalRequired = readBackendToolApprovalRequired(effectivePreferences);
    if (toolApprovalRequired === true || toolApprovalRequired === false) {
        nextParameters.toolApprovalRequired = toolApprovalRequired;
    }
    applyAgentMaxIterationsParameterFromModelSettings(nextParameters, readBackendConversationDefaultsModelSettings(effectivePreferences));
    nextParameters.autoTitleGeneration = readBackendAutoTitleGeneration(preferences);
    nextParameters.newConversationInheritLastSettings = readBackendNewConversationInheritLastSettings(preferences);
    const nextModel = readBackendCurrentModel(effectivePreferences);
    return {
        currentModel: nextModel.present ? nextModel.value : currentModel,
        parameters: nextParameters
    };
};

const overlayConversationDefaultDelta = (preferences: JsonValue, delta: JsonObject): JsonObject => {
    const root = isJsonObject(preferences) ? structuredClone(preferences) : {};
    const chat = isJsonObject(root['chat']) ? root['chat'] : {};
    const defaults = isJsonObject(chat['conversation_defaults_v1']) ? chat['conversation_defaults_v1'] : {};
    defaults['version'] = CONVERSATION_DEFAULTS_VERSION;
    defaults['model_settings'] = mergeConversationDefaultDelta(isJsonObject(defaults['model_settings']) ? defaults['model_settings'] : {}, delta);
    chat['conversation_defaults_v1'] = defaults;
    root['chat'] = chat;
    return root;
};

const buildBackendChatPreferencesPatch = (currentModel: string | null, parameters: ChatParameters, confirmedPreferences: JsonValue = null, options: Readonly<{ includeMcp: boolean }> = { includeMcp: true }): Record<string, JsonValue> => {
    const nextParameters: Record<string, JsonValue> = {};
    for (const key of STORED_CHAT_PARAMETER_KEYS) {
        const clonedValue = cloneParameterValue(parameters[key]);
        if (clonedValue !== undefined) {
            nextParameters[CHAT_PARAMETER_WIRE_KEYS[key] ?? key] = clonedValue;
        }
    }
    const desiredSettings: JsonObject = { model: currentModel, parameters: nextParameters, agent: buildAgentSettingsWithMaxIterations(parameters) };
    if (options.includeMcp) {
        desiredSettings['mcp'] = {
            'tools_enabled': parameters.toolsEnabled === true,
            'tool_approval_required': parameters.toolApprovalRequired === true
        };
    }
    const confirmedSettings = readBackendConversationDefaultsModelSettings(confirmedPreferences);
    const settingsPatch = sparseDifference(confirmedSettings, desiredSettings);
    if (Object.keys(settingsPatch).length === 0) return {};
    return { chat: { 'conversation_defaults_v1': { version: CONVERSATION_DEFAULTS_VERSION, 'model_settings': settingsPatch } } };
};

const updateBackendDefaults = (preferences: JsonValue, update: (chat: JsonObject, defaults: JsonObject) => void): JsonObject => {
    const root = isJsonObject(preferences) ? structuredClone(preferences) : {};
    const chat = isJsonObject(root['chat']) ? root['chat'] : {};
    const defaults = isJsonObject(chat['conversation_defaults_v1']) ? chat['conversation_defaults_v1'] : {};
    defaults['version'] = CONVERSATION_DEFAULTS_VERSION;
    update(chat, defaults);
    chat['conversation_defaults_v1'] = defaults;
    root['chat'] = chat;
    return root;
};

const projectBackendConversationDefaults = (preferences: JsonValue, modelSettings: JsonObject): JsonObject =>
    updateBackendDefaults(preferences, (_chat, defaults) => {
        const sanitized = structuredClone(modelSettings);
        delete sanitized['workspace_path'];
        defaults['model_settings'] = sanitized;
    });

const projectBackendMcpDefaults = (preferences: JsonValue, config: McpConfig): JsonObject =>
    updateBackendDefaults(preferences, (_chat, defaults) => {
        const modelSettings = isJsonObject(defaults['model_settings']) ? defaults['model_settings'] : {};
        modelSettings['mcp'] = { 'default_tools': [...config.defaultTools], 'plan_tools': [...config.planTools], 'execute_tools': [...config.executeTools], 'server_configs': { ...config.serverConfigs }, 'tools_enabled': config.toolsEnabled, 'tool_approval_required': config.toolApprovalRequired };
        defaults['model_settings'] = modelSettings;
    });

const projectBackendRagDefaults = (preferences: JsonValue, response: RagConfigResponse): JsonObject =>
    updateBackendDefaults(preferences, (chat, defaults) => {
        defaults['rag_config'] = { enabled: response.enabled, 'retrieval_strategy': response.retrievalStrategy, 'top_k': response.topK, 'similarity_threshold': response.similarityThreshold, 'chunking_strategy': response.chunkingStrategy, 'chunk_size': response.chunkSize, 'chunk_overlap': response.chunkOverlap, 'embedding_model': response.embeddingModel };
        chat['default_embedding_model'] = response.defaultEmbeddingModel;
    });

export { applyBackendChatPreferencesToPageState, buildBackendChatPreferencesPatch, projectBackendConversationDefaults, projectBackendMcpDefaults, projectBackendRagDefaults };
