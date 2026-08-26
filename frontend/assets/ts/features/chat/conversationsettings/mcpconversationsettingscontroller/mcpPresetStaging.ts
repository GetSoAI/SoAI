/* SoAI - MCP preset snapshot and staged merge ownership [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/mcpPresetStaging.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { normalizeMcpConfigValues } from '@core/mcp/toolChangeSurfaces.ts';
import { isKnowledgeToolsForceEnabled, isKnowledgeToolsLocked, isRequiredKnowledgeTool } from '@features/chat/conversationsettings/mcpKnowledgeState.ts';
import type { McpConfig, McpFormValues, McpTool } from '@features/chat/conversationsettings/settingsModels.ts';

type McpPresetMergeResult = Readonly<{ values: McpFormValues; skippedValues: readonly string[] }>;

const cloneValues = (values: McpFormValues): McpFormValues => ({ ...values, defaultTools: [...values.defaultTools], planTools: [...values.planTools], executeTools: [...values.executeTools], serverConfigs: { ...values.serverConfigs } });

const toolMap = (selected: readonly string[], tools: readonly McpTool[]): JsonObject => {
    const enabled = new Set(selected);
    const result: JsonObject = {};
    for (const tool of tools) result[tool.name] = enabled.has(tool.name);
    return result;
};

const snapshotMcpPreset = (values: McpFormValues, tools: readonly McpTool[], baseline: McpConfig | null, toolsEnabledLocked = false): JsonObject => {
    const section: JsonObject = { 'tool_approval_required': values.toolApprovalRequired };
    if (!toolsEnabledLocked && !isKnowledgeToolsForceEnabled(baseline)) section['tools_enabled'] = values.toolsEnabled;
    const lockedServerIds = new Set(tools.filter((tool) => isKnowledgeToolsLocked(baseline) && isRequiredKnowledgeTool(tool)).map((tool) => tool.serverId));
    const serverIds = new Set(tools.filter((tool) => !lockedServerIds.has(tool.serverId)).map((tool) => tool.serverId));
    if (serverIds.size > 0) section['servers'] = Object.fromEntries([...serverIds].map((serverId) => [serverId, values.serverConfigs[serverId] !== false]));
    const editableTools = tools.filter((tool) => tool.allowed && !(isKnowledgeToolsLocked(baseline) && isRequiredKnowledgeTool(tool)));
    if (editableTools.length > 0) section['modes'] = { default: toolMap(values.defaultTools, editableTools), plan: toolMap(values.planTools, editableTools), execute: toolMap(values.executeTools, editableTools) };
    return section;
};

const mergeBooleanMap = (current: readonly string[], raw: JsonValue | undefined, tools: ReadonlyMap<string, McpTool>, lockedTools: ReadonlySet<string>, label: string, skipped: string[]): string[] | null => {
    if (raw === undefined) return [...current];
    if (!raw || Array.isArray(raw) || typeof raw !== 'object') return null;
    const selected = new Set(current);
    for (const [name, enabled] of Object.entries(raw)) {
        if (typeof enabled !== 'boolean') return null;
        const tool = tools.get(name);
        if (!tool) {
            skipped.push(`${label}:${name}`);
            continue;
        }
        if (!tool.allowed || lockedTools.has(name)) {
            skipped.push(`${label}:${name}`);
            continue;
        }
        if (enabled) selected.add(name);
        else selected.delete(name);
    }
    return [...selected];
};

const mergeMcpPreset = (current: McpFormValues, section: JsonObject, tools: readonly McpTool[], baseline: McpConfig, toolsEnabledLocked = false): McpPresetMergeResult | null => {
    const next = cloneValues(current);
    const skipped: string[] = [];
    if ('tools_enabled' in section) {
        if (typeof section['tools_enabled'] !== 'boolean') return null;
        if ((toolsEnabledLocked || isKnowledgeToolsForceEnabled(baseline)) && section['tools_enabled'] !== current.toolsEnabled) skipped.push('tools_enabled');
        else next.toolsEnabled = section['tools_enabled'];
    }
    if ('tool_approval_required' in section) {
        if (typeof section['tool_approval_required'] !== 'boolean') return null;
        next.toolApprovalRequired = section['tool_approval_required'];
    }
    const servers = section['servers'];
    const lockedServerIds = new Set(tools.filter((tool) => isKnowledgeToolsLocked(baseline) && isRequiredKnowledgeTool(tool)).map((tool) => tool.serverId));
    if (servers !== undefined) {
        if (!servers || Array.isArray(servers) || typeof servers !== 'object') return null;
        for (const [serverId, enabled] of Object.entries(servers)) {
            if (typeof enabled !== 'boolean') return null;
            if (!tools.some((tool) => tool.serverId === serverId) || lockedServerIds.has(serverId)) skipped.push(`server:${serverId}`);
            else if (enabled) delete next.serverConfigs[serverId];
            else next.serverConfigs[serverId] = false;
        }
    }
    const modes = section['modes'];
    if (modes !== undefined && !isJsonObject(modes)) return null;
    const modeValues = isJsonObject(modes) ? modes : null;
    const toolCatalog = new Map(tools.map((tool) => [tool.name, tool]));
    const lockedTools = new Set(tools.filter((tool) => isKnowledgeToolsLocked(baseline) && isRequiredKnowledgeTool(tool)).map((tool) => tool.name));
    const defaultTools = mergeBooleanMap(next.defaultTools, modeValues?.['default'], toolCatalog, lockedTools, 'default', skipped);
    const planTools = mergeBooleanMap(next.planTools, modeValues?.['plan'], toolCatalog, lockedTools, 'plan', skipped);
    const executeTools = mergeBooleanMap(next.executeTools, modeValues?.['execute'], toolCatalog, lockedTools, 'execute', skipped);
    if (!defaultTools || !planTools || !executeTools) return null;
    next.defaultTools = defaultTools;
    next.planTools = planTools;
    next.executeTools = executeTools;
    return { values: next, skippedValues: skipped };
};

const changedSelectionMap = (current: readonly string[], baseline: readonly string[]): JsonObject => {
    const currentNames = new Set(current);
    const baselineNames = new Set(baseline);
    const changes: JsonObject = {};
    for (const name of new Set([...currentNames, ...baselineNames])) {
        if (currentNames.has(name) !== baselineNames.has(name)) changes[name] = currentNames.has(name);
    }
    return changes;
};

const buildMcpIntentSection = (captured: McpFormValues, baseline: McpConfig, tools: readonly McpTool[]): JsonObject => {
    const original = normalizeMcpConfigValues(baseline);
    const section: JsonObject = {};
    if (captured.toolsEnabled !== original.toolsEnabled) section['tools_enabled'] = captured.toolsEnabled;
    if (captured.toolApprovalRequired !== original.toolApprovalRequired) section['tool_approval_required'] = captured.toolApprovalRequired;
    const servers: JsonObject = {};
    for (const serverId of new Set([...tools.map((tool) => tool.serverId), ...Object.keys(original.serverConfigs), ...Object.keys(captured.serverConfigs)])) {
        const capturedEnabled = captured.serverConfigs[serverId] !== false;
        if (capturedEnabled !== (original.serverConfigs[serverId] !== false)) servers[serverId] = capturedEnabled;
    }
    if (Object.keys(servers).length > 0) section['servers'] = servers;
    const modes: JsonObject = {};
    const defaultChanges = changedSelectionMap(captured.defaultTools, original.defaultTools);
    const planChanges = changedSelectionMap(captured.planTools, original.planTools);
    const executeChanges = changedSelectionMap(captured.executeTools, original.executeTools);
    if (Object.keys(defaultChanges).length > 0) modes['default'] = defaultChanges;
    if (Object.keys(planChanges).length > 0) modes['plan'] = planChanges;
    if (Object.keys(executeChanges).length > 0) modes['execute'] = executeChanges;
    if (Object.keys(modes).length > 0) section['modes'] = modes;
    return section;
};

const reconcileMcpIntentAfterKnowledge = (captured: McpFormValues, originalBaseline: McpConfig, refreshedBaseline: McpConfig, refreshedTools: readonly McpTool[]): McpPresetMergeResult => {
    const section = buildMcpIntentSection(captured, originalBaseline, refreshedTools);
    return mergeMcpPreset(normalizeMcpConfigValues(refreshedBaseline), section, refreshedTools, refreshedBaseline) ?? { values: normalizeMcpConfigValues(refreshedBaseline), skippedValues: ['invalid_intent'] };
};

const deriveHypotheticalKnowledgeMcpConfig = (baseline: McpConfig, ragEnabled: boolean, modelSupportsTools: boolean): McpConfig => {
    const documentCount = baseline.knowledgeState?.documentCount ?? 0;
    const requiredToolsAvailable = baseline.knowledgeState?.blockingReason !== 'missing_required_tools';
    const autoManaged = ragEnabled && documentCount > 0 && requiredToolsAvailable && modelSupportsTools;
    const blockingReason = !ragEnabled ? 'disabled' : documentCount <= 0 ? 'empty' : !requiredToolsAvailable ? 'missing_required_tools' : !modelSupportsTools ? 'model_without_tool_calling' : null;
    return {
        ...baseline,
        knowledgeState: { ragEnabled, documentCount, autoManaged, toolsLocked: autoManaged, forceToolsEnabled: autoManaged, ready: autoManaged, blockingReason }
    };
};

export { deriveHypotheticalKnowledgeMcpConfig, mergeMcpPreset, reconcileMcpIntentAfterKnowledge, snapshotMcpPreset };
export type { McpPresetMergeResult };
