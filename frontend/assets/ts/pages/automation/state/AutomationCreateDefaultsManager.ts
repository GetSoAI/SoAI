/* SoAI - Automation page create defaults manager [frontend/assets/ts/pages/automation/state/AutomationCreateDefaultsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isMcpToolServerEnabled, normalizeMcpServerId } from '@core/mcp/serverSettings.ts';
import { isArray, isBoolean, isObject, isString } from '@core/typeGuards.ts';
import type { AutomationDefinition, AutomationMcpCatalog } from '@features/automation/public.ts';

const STORAGE_KEY = 'automation_create_defaults';
const REQUIRED_AUTOMATION_EXECUTE_TOOL = 'todo_write';

interface AutomationCreateDefaults {
    executeTools: readonly string[];
    serverConfigs: Record<string, boolean>;
    interactiveToolApproval: boolean;
}

interface AutomationCreateDefaultsStorage {
    get(key: string, fallback?: JsonValue): JsonValue;
    set(key: string, value: JsonValue): void;
}

class AutomationCreateDefaultsCorruptError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'AutomationCreateDefaultsCorruptError';
    }
}

const normalizeToolList = (value: JsonValue, label: string): string[] => {
    if (!isArray(value)) {
        throw new AutomationCreateDefaultsCorruptError(`${label} must be an array`);
    }
    const normalized: string[] = [];
    for (const entry of value) {
        if (!isString(entry)) {
            throw new AutomationCreateDefaultsCorruptError(`${label} entries must be strings`);
        }
        const toolName = entry.trim();
        if (!toolName) {
            throw new AutomationCreateDefaultsCorruptError(`${label} entries cannot be empty`);
        }
        if (!normalized.includes(toolName)) {
            normalized.push(toolName);
        }
    }
    return normalized;
};

const normalizeServerConfigs = (value: JsonValue, label: string): Record<string, boolean> => {
    if (!isObject(value)) {
        throw new AutomationCreateDefaultsCorruptError(`${label} must be an object`);
    }
    const normalized: Record<string, boolean> = {};
    for (const [serverId, enabled] of Object.entries(value)) {
        const trimmedServerId = serverId.trim();
        if (!trimmedServerId) {
            throw new AutomationCreateDefaultsCorruptError(`${label} keys cannot be empty`);
        }
        if (!isBoolean(enabled)) {
            throw new AutomationCreateDefaultsCorruptError(`${label} values must be booleans`);
        }
        if (!enabled) {
            normalized[normalizeMcpServerId(trimmedServerId)] = false;
        }
    }
    return normalized;
};

const loadStoredAutomationCreateDefaults = (storage: AutomationCreateDefaultsStorage): AutomationCreateDefaults | null => {
    const value = storage.get(STORAGE_KEY, null);
    if (value === null) {
        return null;
    }
    if (!isObject(value)) {
        throw new AutomationCreateDefaultsCorruptError('Automation create defaults payload must be an object');
    }
    const approval = value['interactive_tool_approval'];
    if (!isBoolean(approval)) {
        throw new AutomationCreateDefaultsCorruptError('Automation create defaults interactive_tool_approval must be a boolean');
    }
    return {
        executeTools: normalizeToolList(value['execute_tools'] ?? null, 'Automation create defaults execute_tools'),
        serverConfigs: normalizeServerConfigs(value['server_configs'] ?? null, 'Automation create defaults server_configs'),
        interactiveToolApproval: approval
    };
};

const filterDefaultsForCatalog = (defaults: AutomationCreateDefaults, catalog: AutomationMcpCatalog): AutomationCreateDefaults => {
    const toolsByName = new Map(catalog.tools.filter((tool) => tool.allowed).map((tool) => [tool.name, tool]));
    const catalogServerIds = new Set(catalog.tools.map((tool) => normalizeMcpServerId(tool.serverId)));
    const serverConfigs: Record<string, boolean> = {};
    for (const [serverId, enabled] of Object.entries(defaults.serverConfigs)) {
        if (!catalogServerIds.has(normalizeMcpServerId(serverId))) {
            continue;
        }
        if (!enabled) {
            serverConfigs[normalizeMcpServerId(serverId)] = false;
        }
    }
    const executeTools: string[] = [];
    for (const toolName of defaults.executeTools) {
        const tool = toolsByName.get(toolName);
        if (!tool) {
            continue;
        }
        if (!isMcpToolServerEnabled(tool.serverId, serverConfigs)) {
            continue;
        }
        executeTools.push(toolName);
    }
    if (!executeTools.includes(REQUIRED_AUTOMATION_EXECUTE_TOOL)) {
        return {
            executeTools: [...catalog.executeTools],
            serverConfigs: {},
            interactiveToolApproval: defaults.interactiveToolApproval
        };
    }
    return {
        executeTools: executeTools,
        serverConfigs: serverConfigs,
        interactiveToolApproval: defaults.interactiveToolApproval
    };
};

const buildCatalogAutomationCreateDefaults = (catalog: AutomationMcpCatalog): AutomationCreateDefaults => ({
    executeTools: [...catalog.executeTools],
    serverConfigs: {},
    interactiveToolApproval: false
});

const resolveAutomationCreateDefaults = (storage: AutomationCreateDefaultsStorage, catalog: AutomationMcpCatalog | null): AutomationCreateDefaults => {
    if (catalog === null) {
        return {
            executeTools: [],
            serverConfigs: {},
            interactiveToolApproval: false
        };
    }
    const stored = loadStoredAutomationCreateDefaults(storage);
    if (stored !== null) {
        return filterDefaultsForCatalog(stored, catalog);
    }
    return buildCatalogAutomationCreateDefaults(catalog);
};

const saveAutomationCreateDefaults = (storage: AutomationCreateDefaultsStorage, automation: AutomationDefinition): void => {
    if (!automation.modelSettings.mcp.executeTools.includes(REQUIRED_AUTOMATION_EXECUTE_TOOL)) {
        throw new Error('Automation create defaults require todo_write in execute_tools');
    }
    storage.set(STORAGE_KEY, {
        'execute_tools': [...automation.modelSettings.mcp.executeTools],
        'server_configs': { ...automation.modelSettings.mcp.serverConfigs },
        'interactive_tool_approval': automation.interactiveToolApproval
    });
};

export { resolveAutomationCreateDefaults, saveAutomationCreateDefaults };
export type { AutomationCreateDefaults };
