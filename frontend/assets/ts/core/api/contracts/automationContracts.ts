/* SoAI - Shared frontend API contract boundary automation contracts [frontend/assets/ts/core/api/contracts/automationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AUTOMATION_RECURRENCES, AUTOMATION_RUN_STATUSES, AUTOMATION_ZONE_STATUSES } from '@core/automation/protocols.ts';
import { readAgentMaxIterationsFromAgentSettings } from '@core/chat/parameters/agentMaxIterations.ts';
import { CHAT_PARAMETER_SEND_FLAG_KEYS, CHAT_PARAMETER_WIRE_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { splitTrimmedList } from '@core/normalize.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableFiniteNumberValue, readRequiredNonNegativeIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readNullableBooleanValue, readNullableEpochMsValue, readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredEpochMsValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import { isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { parseMcpFormValues, parseMcpToolList } from '@core/mcp/configParsing.ts';
import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readPaginatedArrayPayload } from '@core/data/paginatedPayload.ts';
import type { AutomationColor, AutomationDefinitionResponse, AutomationDefinitionsPageResponse, AutomationMcpCatalogResponse, AutomationOccurrenceResponse, AutomationOccurrencesDeleteResponse, AutomationOccurrencesPageResponse, AutomationRunResponse } from '@core/api/contracts/automationContractTypes.ts';

const normalizeAutomationColor = (value: JsonValue | null | undefined): AutomationColor => {
    if (value === null) {
        return null;
    }
    if (!isString(value)) {
        throw new Error('Automation color must be a string or null.');
    }
    const colors = new Map<string, Exclude<AutomationColor, null>>([
        ['red', 'Red'],
        ['yellow', 'Yellow'],
        ['purple', 'Purple'],
        ['green', 'Green'],
        ['blue', 'Blue']
    ]);
    const normalized = colors.get(value.trim().toLowerCase());
    if (!normalized) {
        throw new Error('Automation color is invalid.');
    }
    return normalized;
};

const parseAutomationMcpSettings = (value: JsonValue | null | undefined, interactiveToolApproval: boolean): AutomationDefinitionResponse['modelSettings']['mcp'] => {
    if (!isJsonObject(value)) {
        throw new Error('Automation.model_settings.mcp must be a JSON object');
    }
    const mcp = parseMcpFormValues(value);
    const approvalValue = value['tool_approval_required'];
    if ((approvalValue === true || approvalValue === false) && approvalValue !== interactiveToolApproval) {
        throw new Error('Automation.model_settings.mcp.tool_approval_required must match Automation.interactive_tool_approval');
    }
    return {
        ...mcp,
        toolApprovalRequired: interactiveToolApproval
    };
};

const readOptionalFiniteNumberField = (record: JsonObject, fieldName: string, label: string): number | null | undefined => {
    if (!(fieldName in record)) {
        return undefined;
    }
    return readNullableFiniteNumberValue(record[fieldName], label);
};

const readOptionalBooleanField = (record: JsonObject, fieldName: string, label: string): boolean | undefined => {
    if (!(fieldName in record)) {
        return undefined;
    }
    const value = readNullableBooleanValue(record[fieldName], label);
    return value === null ? undefined : value;
};

const readOptionalTrimmedStringField = (record: JsonObject, fieldName: string, label: string): string | null | undefined => {
    if (!(fieldName in record)) {
        return undefined;
    }
    return readNullableTrimmedStringValue(record[fieldName], label);
};

const readOptionalStopField = (record: JsonObject): string[] | undefined => {
    if (!('stop' in record)) {
        return undefined;
    }
    const value = record['stop'];
    if (value === null || value === undefined) {
        return [];
    }
    if (typeof value === 'string') {
        return splitTrimmedList(value, ',');
    }
    return readRequiredTrimmedStringArrayValue(value, 'Automation.model_settings.stop');
};

const parseAutomationPromptSettings = (value: JsonValue | null | undefined): AutomationDefinitionResponse['modelSettings']['prompts'] | undefined => {
    if (value === undefined || value === null) {
        return undefined;
    }
    const promptsRecord = requireRecord(value, 'Automation.model_settings.prompts');
    const additionalPrompts: JsonObject = {};
    Object.entries(promptsRecord).forEach(([key, promptValue]) => {
        if (key !== 'user_system_prompt' && key !== 'user_system_prompt_lock_enabled' && key !== 'soai_system_prompt_enabled') {
            additionalPrompts[key] = promptValue;
        }
    });
    return {
        userSystemPrompt: readNullableTrimmedStringValue(promptsRecord['user_system_prompt'], 'Automation.model_settings.prompts.user_system_prompt'),
        userSystemPromptLockEnabled: readNullableBooleanValue(promptsRecord['user_system_prompt_lock_enabled'], 'Automation.model_settings.prompts.user_system_prompt_lock_enabled') ?? false,
        soaiSystemPromptEnabled: readNullableBooleanValue(promptsRecord['soai_system_prompt_enabled'], 'Automation.model_settings.prompts.soai_system_prompt_enabled') ?? true,
        additionalPrompts
    };
};

const parseAutomationDefinition = (value: JsonValue | null | undefined): AutomationDefinitionResponse => {
    const record = requireRecord(value, 'Automation');
    const modelSettingsRecord = requireRecord(record['model_settings'], 'Automation.model_settings');
    const agentRecord = requireRecord(modelSettingsRecord['agent'], 'Automation.model_settings.agent');
    const agentMode = agentRecord['mode'];
    if (agentMode !== 'execute') {
        throw new Error('Automation.model_settings.agent.mode must be execute');
    }
    const interactiveToolApproval = readRequiredBooleanValue(record['interactive_tool_approval'], 'Automation.interactive_tool_approval');
    const modelSettings: AutomationDefinitionResponse['modelSettings'] = {
        model: readRequiredTrimmedString(modelSettingsRecord, 'model', 'Automation.model_settings.model'),
        agent: { mode: 'execute', maxIterations: readAgentMaxIterationsFromAgentSettings(agentRecord) },
        mcp: parseAutomationMcpSettings(modelSettingsRecord['mcp'], interactiveToolApproval)
    };
    const workspacePath = readOptionalTrimmedStringField(modelSettingsRecord, 'workspace_path', 'Automation.model_settings.workspace_path');
    if (workspacePath !== undefined) modelSettings.workspacePath = workspacePath;
    const prompts = parseAutomationPromptSettings(modelSettingsRecord['prompts']);
    if (prompts !== undefined) modelSettings.prompts = prompts;
    const temperature = readOptionalFiniteNumberField(modelSettingsRecord, 'temperature', 'Automation.model_settings.temperature');
    if (temperature !== undefined && temperature !== null) modelSettings.temperature = temperature;
    const topP = readOptionalFiniteNumberField(modelSettingsRecord, 'top_p', 'Automation.model_settings.top_p');
    if (topP !== undefined && topP !== null) modelSettings.topP = topP;
    const seed = readOptionalFiniteNumberField(modelSettingsRecord, 'seed', 'Automation.model_settings.seed');
    if (seed !== undefined) modelSettings.seed = seed;
    const contextWindowTokens = readOptionalFiniteNumberField(modelSettingsRecord, 'context_window_tokens', 'Automation.model_settings.context_window_tokens');
    if (contextWindowTokens !== undefined) modelSettings.contextWindowTokens = contextWindowTokens;
    const maxCompletionTokens = readOptionalFiniteNumberField(modelSettingsRecord, 'max_completion_tokens', 'Automation.model_settings.max_completion_tokens');
    if (maxCompletionTokens !== undefined) modelSettings.maxCompletionTokens = maxCompletionTokens;
    const frequencyPenalty = readOptionalFiniteNumberField(modelSettingsRecord, 'frequency_penalty', 'Automation.model_settings.frequency_penalty');
    if (frequencyPenalty !== undefined && frequencyPenalty !== null) modelSettings.frequencyPenalty = frequencyPenalty;
    const presencePenalty = readOptionalFiniteNumberField(modelSettingsRecord, 'presence_penalty', 'Automation.model_settings.presence_penalty');
    if (presencePenalty !== undefined && presencePenalty !== null) modelSettings.presencePenalty = presencePenalty;
    const topLogprobs = readOptionalFiniteNumberField(modelSettingsRecord, 'top_logprobs', 'Automation.model_settings.top_logprobs');
    if (topLogprobs !== undefined) modelSettings.topLogprobs = topLogprobs;
    const completionCount = readOptionalFiniteNumberField(modelSettingsRecord, 'n', 'Automation.model_settings.n');
    if (completionCount !== undefined && completionCount !== null) modelSettings.completionCount = completionCount;
    const reasoningEffort = readOptionalTrimmedStringField(modelSettingsRecord, 'reasoning_effort', 'Automation.model_settings.reasoning_effort');
    if (reasoningEffort !== undefined) modelSettings.reasoningEffort = reasoningEffort;
    const logprobs = readOptionalBooleanField(modelSettingsRecord, 'logprobs', 'Automation.model_settings.logprobs');
    if (logprobs !== undefined) modelSettings.logprobs = logprobs;
    const stop = readOptionalStopField(modelSettingsRecord);
    if (stop !== undefined) modelSettings.stop = stop;
    for (const key of CHAT_PARAMETER_SEND_FLAG_KEYS) {
        const wireKey = CHAT_PARAMETER_WIRE_KEYS[key] ?? key;
        const value = readOptionalBooleanField(modelSettingsRecord, wireKey, `Automation.model_settings.${wireKey}`);
        if (value !== undefined) modelSettings[key] = value;
    }
    return {
        id: readRequiredTrimmedString(record, 'id', 'Automation.id'),
        title: readRequiredTrimmedString(record, 'title', 'Automation.title'),
        enabled: readRequiredBooleanValue(record['enabled'], 'Automation.enabled'),
        interactiveToolApproval: interactiveToolApproval,
        color: normalizeAutomationColor(record['color']),
        timezone: readRequiredTrimmedString(record, 'timezone', 'Automation.timezone'),
        startLocal: readRequiredTrimmedString(record, 'start_local', 'Automation.start_local'),
        recurrence: readRequiredEnumValue(record['recurrence'], 'Automation.recurrence', AUTOMATION_RECURRENCES),
        turns: readRequiredTrimmedStringArrayValue(record['turns'], 'Automation.turns'),
        maxTurns: readRequiredPositiveIntegerValue(record['max_turns'], 'Automation.max_turns'),
        maxTurnChars: readRequiredPositiveIntegerValue(record['max_turn_chars'], 'Automation.max_turn_chars'),
        maxRunMinutes: readRequiredPositiveIntegerValue(record['max_run_minutes'], 'Automation.max_run_minutes'),
        modelSettings: modelSettings,
        nextRunAtMs: readNullableEpochMsValue(record['next_run_at_ms'], 'Automation.next_run_at_ms'),
        createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], 'Automation.created_at_ms'),
        lastModifiedAtMs: readRequiredEpochMsValue(record['last_modified_at_ms'], 'Automation.last_modified_at_ms')
    };
};

const parseAutomationMcpCatalog = (value: JsonValue | null | undefined): AutomationMcpCatalogResponse => {
    const record = requireRecord(value, 'AutomationMcpCatalog');
    return {
        tools: parseMcpToolList(record),
        defaultTools: [],
        planTools: [],
        executeTools: readRequiredTrimmedStringArrayValue(record['execute_tools'], 'AutomationMcpCatalog.execute_tools')
    };
};

const parseAutomationZone = (value: JsonValue | null | undefined): AutomationOccurrenceResponse => {
    const record = requireRecord(value, 'AutomationZone');
    return {
        automationId: readRequiredTrimmedString(record, 'automation_id', 'AutomationZone.automation_id'),
        scheduledAtMs: readRequiredEpochMsValue(record['scheduled_at_ms'], 'AutomationZone.scheduled_at_ms'),
        title: readRequiredTrimmedString(record, 'title', 'AutomationZone.title'),
        enabled: readNullableBooleanValue(record['enabled'], 'AutomationZone.enabled'),
        color: normalizeAutomationColor(record['color']),
        runId: readNullableTrimmedStringValue(record['run_id'], 'AutomationZone.run_id'),
        status: readRequiredEnumValue(record['status'], 'AutomationZone.status', AUTOMATION_ZONE_STATUSES),
        resultExcerpt: readNullableTrimmedStringValue(record['result_excerpt'], 'AutomationZone.result_excerpt'),
        statusMessage: readNullableTrimmedStringValue(record['status_message'], 'AutomationZone.status_message'),
        convId: readNullableTrimmedStringValue(record['conv_id'], 'AutomationZone.conv_id'),
        startedAtActualMs: readNullableEpochMsValue(record['started_at_actual_ms'], 'AutomationZone.started_at_actual_ms'),
        finishedAtMs: readNullableEpochMsValue(record['finished_at_ms'], 'AutomationZone.finished_at_ms')
    };
};

const parseAutomationRunRecord = (value: JsonValue | null | undefined): AutomationRunResponse => {
    const record = requireRecord(value, 'AutomationRun');
    return {
        runId: readRequiredTrimmedString(record, 'run_id', 'AutomationRun.run_id'),
        automationId: readRequiredTrimmedString(record, 'automation_id', 'AutomationRun.automation_id'),
        scheduledAtMs: readRequiredEpochMsValue(record['scheduled_at_ms'], 'AutomationRun.scheduled_at_ms'),
        startedAtActualMs: readNullableEpochMsValue(record['started_at_actual_ms'], 'AutomationRun.started_at_actual_ms'),
        finishedAtMs: readNullableEpochMsValue(record['finished_at_ms'], 'AutomationRun.finished_at_ms'),
        status: readRequiredEnumValue(record['status'], 'AutomationRun.status', AUTOMATION_RUN_STATUSES),
        statusMessage: readNullableTrimmedStringValue(record['status_message'], 'AutomationRun.status_message'),
        resultExcerpt: readNullableTrimmedStringValue(record['result_excerpt'], 'AutomationRun.result_excerpt'),
        convId: readNullableTrimmedStringValue(record['conv_id'], 'AutomationRun.conv_id'),
        title: readNullableTrimmedStringValue(record['title'], 'AutomationRun.title'),
        enabled: readNullableBooleanValue(record['enabled'], 'AutomationRun.enabled'),
        color: normalizeAutomationColor(record['color'])
    };
};

const parseAutomationOccurrencesDeleteResult = (value: JsonValue | null | undefined): AutomationOccurrencesDeleteResponse => {
    const record = requireRecord(value, 'AutomationOccurrencesDeleteResult');
    return {
        deletedOccurrenceCount: readRequiredPositiveIntegerValue(record['deleted_occurrence_count'], 'AutomationOccurrencesDeleteResult.deleted_occurrence_count'),
        deletedRunCount: readRequiredNonNegativeIntegerValue(record['deleted_run_count'], 'AutomationOccurrencesDeleteResult.deleted_run_count'),
        cancelledRunIds: readRequiredTrimmedStringArrayValue(record['cancelled_run_ids'], 'AutomationOccurrencesDeleteResult.cancelled_run_ids')
    };
};

const decodeAutomationDefinition = (value: ApiResponsePayload, label: string): AutomationDefinitionResponse => parseAutomationDefinition(requireJsonResponsePayload(value, label));

const decodeAutomationDefinitionList = (value: ApiResponsePayload): AutomationDefinitionsPageResponse => {
    const page = readPaginatedArrayPayload(requireJsonResponsePayload(value, 'Automation list'), 'automations', 'Automation list response');
    return { automations: page.items.map((entry) => parseAutomationDefinition(entry)), ...page.metadata };
};

const decodeAutomationOccurrenceList = (value: ApiResponsePayload): AutomationOccurrencesPageResponse => {
    const page = readPaginatedArrayPayload(requireJsonResponsePayload(value, 'Automation occurrences'), 'occurrences', 'Automation occurrences response');
    return { occurrences: page.items.map((entry) => parseAutomationZone(entry)), ...page.metadata };
};

const decodeAutomationRun = (value: ApiResponsePayload, label: string): AutomationRunResponse => parseAutomationRunRecord(requireJsonResponsePayload(value, label));

const decodeAutomationRunList = (value: ApiResponsePayload, label: string): readonly AutomationRunResponse[] => {
    const payload = requireJsonResponsePayload(value, label);
    if (!Array.isArray(payload)) {
        throw new TypeError(`${label} must be an array.`);
    }
    return payload.map((entry) => parseAutomationRunRecord(entry));
};

const decodeAutomationMcpCatalog = (value: ApiResponsePayload): AutomationMcpCatalogResponse => parseAutomationMcpCatalog(requireJsonResponsePayload(value, 'Automation MCP catalog'));

const decodeAutomationOccurrencesDeleteResult = (value: ApiResponsePayload): AutomationOccurrencesDeleteResponse => parseAutomationOccurrencesDeleteResult(requireJsonResponsePayload(value, 'Automation occurrences delete'));

export { decodeAutomationDefinition, decodeAutomationDefinitionList, decodeAutomationMcpCatalog, decodeAutomationOccurrenceList, decodeAutomationOccurrencesDeleteResult, decodeAutomationRun, decodeAutomationRunList };
