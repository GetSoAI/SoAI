/* SoAI - Canonical Chat execution settings boundary mapping [frontend/assets/ts/core/chat/executionSettingsMapping.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_PARAMETER_WIRE_KEYS, STORED_CHAT_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { MAX_AGENT_MAX_ITERATIONS } from '@core/chat/parameters/agentMaxIterations.ts';
import { normalizeBooleanOrDefault, normalizeOptionalBooleanRecord, normalizeOptionalToolNameList } from '@core/mcp/valueNormalization.ts';
import { hasOwn, isBoolean, isNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import { isAgentMode } from '@core/chat/agentMode.ts';
import { normalizeComparisonModelIds } from '@core/chat/comparisonModels.ts';
import type { ConversationAgentSettings, ConversationIdentitySettings, ConversationMcpSettings, ConversationMcpSettingsUpdate, ConversationModelSettings, ConversationModelSettingsUpdate, ConversationParameterSettings, ConversationPromptSettings } from '@core/chat/executionSettingsTypes.ts';

const normalizeOptionalBoolean = (value: JsonValue | undefined, defaultValue: boolean): boolean => {
    if (isBoolean(value)) return value;
    if (isNumber(value) && Number.isInteger(value)) {
        if (value === 0) return false;
        if (value === 1) return true;
    }
    if (isString(value)) {
        const normalized = value.trim().toLowerCase();
        if (normalized === 'true' || normalized === '1' || normalized === 'yes' || normalized === 'on' || normalized === 'enabled') return true;
        if (normalized === 'false' || normalized === '0' || normalized === 'no' || normalized === 'off' || normalized === 'disabled') return false;
    }
    return defaultValue;
};

const parseConversationParameters = (value: JsonValue | undefined): ConversationParameterSettings | undefined => {
    if (value === undefined || value === null) return undefined;
    if (!isJsonObject(value)) throw new Error('Conversation model settings parameters must be an object');
    const additionalParameters: JsonObject = { ...value };
    const parameters: ConversationParameterSettings = {};
    for (const key of STORED_CHAT_PARAMETER_KEYS) {
        const wireKey = CHAT_PARAMETER_WIRE_KEYS[key] ?? key;
        if (!hasOwn(value, wireKey)) continue;
        parameters[key] = value[wireKey];
        delete additionalParameters[wireKey];
    }
    if (Object.keys(additionalParameters).length > 0) parameters.additionalParameters = additionalParameters;
    return parameters;
};

const parseConversationAgentSettings = (value: JsonValue | undefined): ConversationAgentSettings | undefined => {
    if (value === undefined || value === null) return undefined;
    if (!isJsonObject(value)) throw new Error('Conversation model settings agent must be an object');
    const additionalSettings: JsonObject = { ...value };
    const agent: ConversationAgentSettings = {};
    if (hasOwn(value, 'mode')) {
        if (!isAgentMode(value['mode'])) throw new Error('Conversation model settings agent mode is invalid');
        agent.mode = value['mode'];
        delete additionalSettings['mode'];
    }
    if (hasOwn(value, 'max_iterations')) {
        const maxIterations = value['max_iterations'];
        if (!isNumber(maxIterations) || !Number.isInteger(maxIterations) || maxIterations < 1 || maxIterations > MAX_AGENT_MAX_ITERATIONS) {
            throw new Error('Conversation model settings agent max_iterations is invalid');
        }
        agent.maxIterations = maxIterations;
        delete additionalSettings['max_iterations'];
    }
    if (Object.keys(additionalSettings).length > 0) agent.additionalSettings = additionalSettings;
    return agent;
};

const parseConversationMcpSettings = (value: JsonValue | undefined): ConversationMcpSettings | undefined => {
    if (value === undefined || value === null) return undefined;
    if (!isJsonObject(value)) throw new Error('Conversation MCP settings must be an object');
    const additionalSettings: JsonObject = { ...value };
    for (const key of ['default_tools', 'plan_tools', 'execute_tools', 'server_configs', 'tools_enabled', 'tool_approval_required']) delete additionalSettings[key];
    const settings: ConversationMcpSettings = {
        defaultTools: normalizeOptionalToolNameList(value['default_tools'], 'Conversation MCP settings default_tools'),
        planTools: normalizeOptionalToolNameList(value['plan_tools'], 'Conversation MCP settings plan_tools'),
        executeTools: normalizeOptionalToolNameList(value['execute_tools'], 'Conversation MCP settings execute_tools'),
        serverConfigs: normalizeOptionalBooleanRecord(value['server_configs'], 'Conversation MCP settings server_configs'),
        toolsEnabled: normalizeBooleanOrDefault(value['tools_enabled'], true, 'Conversation MCP settings require tools_enabled boolean'),
        toolApprovalRequired: normalizeBooleanOrDefault(value['tool_approval_required'], true, 'Conversation MCP settings require tool_approval_required boolean')
    };
    if (Object.keys(additionalSettings).length > 0) settings.additionalSettings = additionalSettings;
    return settings;
};

const parseConversationIdentitySettings = (value: JsonValue | undefined): ConversationIdentitySettings | undefined => {
    if (value === undefined || value === null) return undefined;
    if (!isJsonObject(value)) throw new Error('Conversation model settings identity must be an object');
    const additionalSettings: JsonObject = { ...value };
    delete additionalSettings['user_display_name'];
    delete additionalSettings['assistant_display_name'];
    const settings: ConversationIdentitySettings = {
        userDisplayName: optionalTrimmedString(value['user_display_name']),
        assistantDisplayName: optionalTrimmedString(value['assistant_display_name'])
    };
    if (Object.keys(additionalSettings).length > 0) settings.additionalSettings = additionalSettings;
    return settings;
};

const parseConversationPromptSettings = (value: JsonValue | undefined): ConversationPromptSettings | undefined => {
    if (value === undefined || value === null) return undefined;
    if (!isJsonObject(value)) throw new Error('Conversation model settings prompts must be an object');
    const additionalSettings: JsonObject = { ...value };
    delete additionalSettings['user_system_prompt'];
    delete additionalSettings['soai_system_prompt_enabled'];
    delete additionalSettings['user_system_prompt_lock_enabled'];
    const prompts: ConversationPromptSettings = {
        userSystemPrompt: optionalTrimmedString(value['user_system_prompt']),
        soaiSystemPromptEnabled: normalizeOptionalBoolean(value['soai_system_prompt_enabled'], true)
    };
    if (hasOwn(value, 'user_system_prompt_lock_enabled')) prompts.userSystemPromptLockEnabled = normalizeOptionalBoolean(value['user_system_prompt_lock_enabled'], false);
    if (Object.keys(additionalSettings).length > 0) prompts.additionalSettings = additionalSettings;
    return prompts;
};

const parseConversationModelSettings = (value: JsonValue | undefined): ConversationModelSettings => {
    if (!isJsonObject(value)) throw new Error('Conversation model_settings is missing or invalid');
    const model = optionalTrimmedString(value['model']);
    const comparisonModels = normalizeComparisonModelIds({ primaryModelId: model, raw: value['comparison_models'] });
    const additionalSettings: JsonObject = { ...value };
    for (const key of ['model', 'comparison_models', 'workspace_path', 'parameters', 'agent', 'mcp', 'identity', 'prompts']) delete additionalSettings[key];
    const settings: ConversationModelSettings = {
        model,
        mcp: parseConversationMcpSettings(value['mcp']) ?? {
            defaultTools: [],
            planTools: [],
            executeTools: [],
            serverConfigs: {},
            toolsEnabled: true,
            toolApprovalRequired: true
        }
    };
    const parameters = parseConversationParameters(value['parameters']);
    const agent = parseConversationAgentSettings(value['agent']);
    const identity = parseConversationIdentitySettings(value['identity']);
    const prompts = parseConversationPromptSettings(value['prompts']);
    if (parameters !== undefined) settings.parameters = parameters;
    if (agent !== undefined) settings.agent = agent;
    if (identity !== undefined) settings.identity = identity;
    if (prompts !== undefined) settings.prompts = prompts;
    if (comparisonModels.length > 0) settings.comparisonModels = comparisonModels;
    if (hasOwn(value, 'workspace_path')) settings.workspacePath = optionalTrimmedString(value['workspace_path']);
    if (Object.keys(additionalSettings).length > 0) settings.additionalSettings = additionalSettings;
    return settings;
};

const serializeConversationParameters = (parameters: ConversationParameterSettings): JsonObject => {
    const serialized: JsonObject = { ...(parameters.additionalParameters ?? {}) };
    for (const key of STORED_CHAT_PARAMETER_KEYS) {
        const value = parameters[key];
        if (value !== undefined) serialized[CHAT_PARAMETER_WIRE_KEYS[key] ?? key] = value;
    }
    return serialized;
};

const serializeConversationAgentSettings = (agent: Partial<ConversationAgentSettings>): JsonObject => {
    const serialized: JsonObject = { ...(agent.additionalSettings ?? {}) };
    if (agent.mode !== undefined) serialized['mode'] = agent.mode;
    if (agent.maxIterations !== undefined) serialized['max_iterations'] = agent.maxIterations;
    return serialized;
};

const serializeConversationMcpSettings = (mcp: ConversationMcpSettings): JsonObject => ({
    ...(mcp.additionalSettings ?? {}),
    'default_tools': [...mcp.defaultTools],
    'plan_tools': [...mcp.planTools],
    'execute_tools': [...mcp.executeTools],
    'server_configs': { ...mcp.serverConfigs },
    'tools_enabled': mcp.toolsEnabled,
    'tool_approval_required': mcp.toolApprovalRequired
});

const serializeConversationMcpSettingsUpdate = (mcp: ConversationMcpSettingsUpdate): JsonObject => {
    const serialized: JsonObject = { ...(mcp.additionalSettings ?? {}) };
    if (mcp.defaultTools !== undefined) serialized['default_tools'] = mcp.defaultTools === null ? null : [...mcp.defaultTools];
    if (mcp.planTools !== undefined) serialized['plan_tools'] = mcp.planTools === null ? null : [...mcp.planTools];
    if (mcp.executeTools !== undefined) serialized['execute_tools'] = mcp.executeTools === null ? null : [...mcp.executeTools];
    if (mcp.serverConfigs !== undefined) serialized['server_configs'] = mcp.serverConfigs === null ? null : { ...mcp.serverConfigs };
    if (mcp.toolsEnabled !== undefined) serialized['tools_enabled'] = mcp.toolsEnabled;
    if (mcp.toolApprovalRequired !== undefined) serialized['tool_approval_required'] = mcp.toolApprovalRequired;
    return serialized;
};

const serializeConversationIdentitySettings = (identity: Partial<ConversationIdentitySettings>): JsonObject => {
    const serialized: JsonObject = { ...(identity.additionalSettings ?? {}) };
    if (identity.userDisplayName !== undefined) serialized['user_display_name'] = identity.userDisplayName;
    if (identity.assistantDisplayName !== undefined) serialized['assistant_display_name'] = identity.assistantDisplayName;
    return serialized;
};

const serializeConversationPromptSettings = (prompts: Partial<ConversationPromptSettings>): JsonObject => {
    const serialized: JsonObject = { ...(prompts.additionalSettings ?? {}) };
    if (prompts.userSystemPrompt !== undefined) serialized['user_system_prompt'] = prompts.userSystemPrompt;
    if (prompts.soaiSystemPromptEnabled !== undefined) serialized['soai_system_prompt_enabled'] = prompts.soaiSystemPromptEnabled;
    if (prompts.userSystemPromptLockEnabled !== undefined) serialized['user_system_prompt_lock_enabled'] = prompts.userSystemPromptLockEnabled;
    return serialized;
};

const serializeConversationModelSettingsUpdate = (settings: ConversationModelSettingsUpdate): JsonObject => {
    const serialized: JsonObject = { ...(settings.additionalSettings ?? {}) };
    if (settings.model !== undefined) serialized['model'] = settings.model;
    if (settings.comparisonModels !== undefined) serialized['comparison_models'] = [...settings.comparisonModels];
    if (settings.workspacePath !== undefined) serialized['workspace_path'] = settings.workspacePath;
    if (settings.parameters !== undefined) serialized['parameters'] = serializeConversationParameters(settings.parameters);
    if (settings.agent !== undefined) serialized['agent'] = serializeConversationAgentSettings(settings.agent);
    if (settings.mcp !== undefined) serialized['mcp'] = serializeConversationMcpSettingsUpdate(settings.mcp);
    if (settings.identity !== undefined) serialized['identity'] = serializeConversationIdentitySettings(settings.identity);
    if (settings.prompts !== undefined) serialized['prompts'] = serializeConversationPromptSettings(settings.prompts);
    return serialized;
};

const serializeConversationModelSettings = (settings: ConversationModelSettings): JsonObject => {
    const serialized: JsonObject = { ...(settings.additionalSettings ?? {}), model: settings.model };
    if (settings.comparisonModels !== undefined) serialized['comparison_models'] = [...settings.comparisonModels];
    if (settings.workspacePath !== undefined) serialized['workspace_path'] = settings.workspacePath;
    if (settings.parameters !== undefined) serialized['parameters'] = serializeConversationParameters(settings.parameters);
    if (settings.agent !== undefined) serialized['agent'] = serializeConversationAgentSettings(settings.agent);
    if (settings.mcp !== undefined) serialized['mcp'] = serializeConversationMcpSettings(settings.mcp);
    if (settings.identity !== undefined) serialized['identity'] = serializeConversationIdentitySettings(settings.identity);
    if (settings.prompts !== undefined) serialized['prompts'] = serializeConversationPromptSettings(settings.prompts);
    return serialized;
};

export { parseConversationModelSettings, serializeConversationMcpSettings, serializeConversationModelSettings, serializeConversationModelSettingsUpdate, serializeConversationParameters };
