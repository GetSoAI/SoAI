/* SoAI - Frontend automation request serialization [frontend/assets/ts/core/api/contracts/automationRequestSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationModelSettings, AutomationOccurrenceKeyRequest, CreateAutomationRequest, UpdateAutomationRequest } from '@core/api/contracts/automationContractTypes.ts';
import { STORED_CHAT_PARAMETER_KEYS, CHAT_PARAMETER_WIRE_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import type { McpFormValues } from '@core/mcp/configTypes.ts';
import { isJsonValue, type JsonObject } from '@core/types/jsonValues.ts';

const serializeMcpFormValues = (configuration: McpFormValues): JsonObject => ({
    'default_tools': configuration.defaultTools,
    'plan_tools': configuration.planTools,
    'execute_tools': configuration.executeTools,
    'server_configs': configuration.serverConfigs,
    'tools_enabled': configuration.toolsEnabled,
    'tool_approval_required': configuration.toolApprovalRequired
});

const serializeAutomationPrompts = (prompts: NonNullable<AutomationModelSettings['prompts']>): JsonObject => {
    const serialized: JsonObject = { ...prompts.additionalPrompts };
    if (prompts.userSystemPrompt !== undefined) serialized['user_system_prompt'] = prompts.userSystemPrompt;
    if (prompts.userSystemPromptLockEnabled !== undefined) serialized['user_system_prompt_lock_enabled'] = prompts.userSystemPromptLockEnabled;
    if (prompts.soaiSystemPromptEnabled !== undefined) serialized['soai_system_prompt_enabled'] = prompts.soaiSystemPromptEnabled;
    return serialized;
};

const serializeAutomationModelSettings = (settings: AutomationModelSettings): JsonObject => {
    const serialized: JsonObject = {
        model: settings.model,
        agent: {
            mode: settings.agent.mode,
            ...(settings.agent.maxIterations === undefined ? {} : { 'max_iterations': settings.agent.maxIterations })
        },
        mcp: serializeMcpFormValues(settings.mcp)
    };
    if (settings.workspacePath !== undefined) serialized['workspace_path'] = settings.workspacePath;
    if (settings.prompts !== undefined) serialized['prompts'] = serializeAutomationPrompts(settings.prompts);
    for (const parameterKey of STORED_CHAT_PARAMETER_KEYS) {
        const value = settings[parameterKey];
        if (value !== undefined && isJsonValue(value)) {
            serialized[CHAT_PARAMETER_WIRE_KEYS[parameterKey] ?? parameterKey] = value;
        }
    }
    if (settings.temperature !== undefined) serialized['temperature'] = settings.temperature;
    if (settings.topP !== undefined) serialized['top_p'] = settings.topP;
    if (settings.seed !== undefined) serialized['seed'] = settings.seed;
    return serialized;
};

const serializeCreateAutomationRequest = (request: CreateAutomationRequest): JsonObject => ({
    title: request.title,
    enabled: request.enabled,
    'interactive_tool_approval': request.interactiveToolApproval,
    color: request.color,
    timezone: request.timezone,
    'start_local': request.startLocal,
    recurrence: request.recurrence,
    turns: [...request.turns],
    'max_turns': request.maxTurns,
    'max_turn_chars': request.maxTurnChars,
    'max_run_minutes': request.maxRunMinutes,
    'model_settings': serializeAutomationModelSettings(request.modelSettings)
});

const serializeUpdateAutomationRequest = (request: UpdateAutomationRequest): JsonObject => {
    const serialized: JsonObject = {};
    if (request.title !== undefined) serialized['title'] = request.title;
    if (request.enabled !== undefined) serialized['enabled'] = request.enabled;
    if (request.interactiveToolApproval !== undefined) serialized['interactive_tool_approval'] = request.interactiveToolApproval;
    if (request.color !== undefined) serialized['color'] = request.color;
    if (request.timezone !== undefined) serialized['timezone'] = request.timezone;
    if (request.startLocal !== undefined) serialized['start_local'] = request.startLocal;
    if (request.recurrence !== undefined) serialized['recurrence'] = request.recurrence;
    if (request.turns !== undefined) serialized['turns'] = [...request.turns];
    if (request.maxTurns !== undefined) serialized['max_turns'] = request.maxTurns;
    if (request.maxTurnChars !== undefined) serialized['max_turn_chars'] = request.maxTurnChars;
    if (request.maxRunMinutes !== undefined) serialized['max_run_minutes'] = request.maxRunMinutes;
    if (request.modelSettings !== undefined) serialized['model_settings'] = serializeAutomationModelSettings(request.modelSettings);
    return serialized;
};

const serializeAutomationOccurrenceKey = (occurrence: AutomationOccurrenceKeyRequest): JsonObject => ({
    'automation_id': occurrence.automationId,
    'scheduled_at_ms': occurrence.scheduledAtMs
});

export { serializeAutomationModelSettings, serializeAutomationOccurrenceKey, serializeCreateAutomationRequest, serializeUpdateAutomationRequest };
