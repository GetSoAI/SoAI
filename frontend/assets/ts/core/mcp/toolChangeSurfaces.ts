/* SoAI - Shared frontend MCP tool change surfaces [frontend/assets/ts/core/mcp/toolChangeSurfaces.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { setFieldSurfaceModified } from '@core/forms/fieldSurface.ts';
import type { McpConfig, McpFormValues, McpToolMode } from '@core/mcp/configTypes.ts';
import { isMcpToolMode, resolveMcpToolsForMode } from '@core/mcp/toolModeSelection.ts';

const SERVER_GROUP_SELECTOR = '.mcp-server-card[data-server-id], .mcp-tool-group-header[data-server-id]';
const TOOL_TOGGLE_SELECTOR = '.mcp-tool-toggle';
const DEFAULT_TOOL_TOGGLE_SELECTOR = '.mcp-default-tool-toggle';

interface McpToolChangeSurfaceOptions {
    modalRoot: Element | null;
    defaultToolsModalRoot?: Element | null | undefined;
    baseline: McpFormValues | null;
    current: McpFormValues | null;
    includeTopLevelSurfaces?: boolean | undefined;
}

const readData = (element: Element, key: string): string | null => {
    const value = element.getAttribute(`data-${key}`);
    return value && value.trim() ? value.trim() : null;
};

const stringMultisetsEqual = (leftValues: readonly string[], rightValues: readonly string[]): boolean => {
    if (leftValues.length !== rightValues.length) {
        return false;
    }
    const counts = new Map<string, number>();
    for (const value of leftValues) {
        const current = counts.get(value);
        counts.set(value, current !== undefined ? current + 1 : 1);
    }
    for (const value of rightValues) {
        const current = counts.get(value);
        if (current === undefined) {
            return false;
        }
        if (current === 1) {
            counts.delete(value);
        } else {
            counts.set(value, current - 1);
        }
    }
    return counts.size === 0;
};

const recordsEqual = (left: Record<string, boolean>, right: Record<string, boolean>): boolean => {
    const leftKeys = Object.keys(left);
    const rightKeys = Object.keys(right);
    if (leftKeys.length !== rightKeys.length) {
        return false;
    }
    for (const key of leftKeys) {
        if (left[key] !== right[key]) {
            return false;
        }
    }
    return true;
};

const normalizeMcpConfigValues = (config: McpConfig): McpFormValues => {
    const serverConfigs: Record<string, boolean> = {};
    for (const [serverId, enabled] of Object.entries(config.serverConfigs)) {
        if (enabled === false) {
            serverConfigs[serverId] = false;
        }
    }
    return {
        defaultTools: [...config.defaultTools],
        planTools: [...config.planTools],
        executeTools: [...config.executeTools],
        serverConfigs: serverConfigs,
        toolsEnabled: config.toolsEnabled,
        toolApprovalRequired: config.toolApprovalRequired
    };
};

const hasToolSelectionChanged = (input: HTMLInputElement, current: McpFormValues, baseline: McpFormValues): boolean => {
    const toolName = readData(input, 'tool-name');
    const modeValue = readData(input, 'tool-mode');
    if (!toolName || !isMcpToolMode(modeValue)) {
        return false;
    }
    const mode: McpToolMode = modeValue;
    const currentSelection = new Set(resolveMcpToolsForMode(current, mode));
    const baselineSelection = new Set(resolveMcpToolsForMode(baseline, mode));
    return currentSelection.has(toolName) !== baselineSelection.has(toolName);
};

const syncTopLevelSurface = (root: Element, selector: string, modified: boolean): void => {
    const element = dom.resolve(selector, root);
    if (element) {
        setFieldSurfaceModified(element, modified);
    }
};

const hasServerEnabledChanged = (serverId: string, current: McpFormValues, baseline: McpFormValues): boolean => {
    return (current.serverConfigs[serverId] !== false) !== (baseline.serverConfigs[serverId] !== false);
};

const hasServerToolSelectionChanged = (surface: Element, selector: string, current: McpFormValues, baseline: McpFormValues): boolean => {
    const group = surface.closest('.mcp-tool-group');
    const panel = surface.closest('.mcp-tool-mode-panel');
    const serverId = readData(surface, 'server-id');
    const modeValue = panel ? readData(panel, 'tool-mode') : null;
    if (!group || !serverId || !isMcpToolMode(modeValue)) {
        return false;
    }
    for (const input of dom.resolveAll(selector, group)) {
        if (input instanceof HTMLInputElement && hasToolSelectionChanged(input, current, baseline)) {
            return true;
        }
    }
    return false;
};

const syncServerGroupSurfaces = (root: Element, selector: string, current: McpFormValues, baseline: McpFormValues, includeServerEnabled: boolean): void => {
    for (const row of dom.resolveAll(SERVER_GROUP_SELECTOR, root)) {
        const serverId = readData(row, 'server-id');
        if (!serverId) {
            continue;
        }
        const serverChanged = includeServerEnabled && hasServerEnabledChanged(serverId, current, baseline);
        setFieldSurfaceModified(row, serverChanged || hasServerToolSelectionChanged(row, selector, current, baseline));
    }
};

const syncToolSurfaces = (root: Element, selector: string, current: McpFormValues, baseline: McpFormValues): void => {
    for (const inputElement of dom.resolveAll(selector, root)) {
        if (!(inputElement instanceof HTMLInputElement)) {
            continue;
        }
        setFieldSurfaceModified(inputElement.closest('.mcp-tool-item') ?? inputElement, hasToolSelectionChanged(inputElement, current, baseline));
    }
};

const syncDefaultToolsTriggerSurface = (root: Element, current: McpFormValues, baseline: McpFormValues): void => {
    const modified = !stringMultisetsEqual(current.defaultTools, baseline.defaultTools) || !stringMultisetsEqual(current.planTools, baseline.planTools) || !stringMultisetsEqual(current.executeTools, baseline.executeTools);
    syncTopLevelSurface(root, '.mcp-default-tools-trigger', modified);
};

const syncMcpToolChangeSurfaces = (options: McpToolChangeSurfaceOptions): void => {
    const modalRoot = options.modalRoot;
    if (!modalRoot) {
        return;
    }
    if (!options.baseline || !options.current) {
        clearMcpToolChangeSurfaces(modalRoot, options.defaultToolsModalRoot);
        return;
    }
    const baseline = options.baseline;
    const current = options.current;
    if (options.includeTopLevelSurfaces === true) {
        syncTopLevelSurface(modalRoot, '.mcp-tools-enabled-toggle', current.toolsEnabled !== baseline.toolsEnabled);
        syncTopLevelSurface(modalRoot, '.mcp-tool-approval-required-toggle', current.toolApprovalRequired !== baseline.toolApprovalRequired);
        syncDefaultToolsTriggerSurface(modalRoot, current, baseline);
    }
    syncToolSurfaces(modalRoot, TOOL_TOGGLE_SELECTOR, current, baseline);
    syncServerGroupSurfaces(modalRoot, TOOL_TOGGLE_SELECTOR, current, baseline, true);
    if (options.defaultToolsModalRoot) {
        syncToolSurfaces(options.defaultToolsModalRoot, DEFAULT_TOOL_TOGGLE_SELECTOR, current, baseline);
        syncServerGroupSurfaces(options.defaultToolsModalRoot, DEFAULT_TOOL_TOGGLE_SELECTOR, current, baseline, false);
    }
};

const clearMcpToolChangeSurfaces = (modalRoot: Element | null, defaultToolsModalRoot?: Element | null | undefined): void => {
    for (const root of [modalRoot, defaultToolsModalRoot]) {
        if (!root) {
            continue;
        }
        for (const surface of dom.resolveAll('.mcp-tools-scope .setting-change-surface.modified', root)) {
            setFieldSurfaceModified(surface, false);
        }
    }
};

const haveMcpFormValuesChanged = (current: McpFormValues, baseline: McpFormValues): boolean => {
    return !stringMultisetsEqual(current.defaultTools, baseline.defaultTools) || !stringMultisetsEqual(current.planTools, baseline.planTools) || !stringMultisetsEqual(current.executeTools, baseline.executeTools) || !recordsEqual(current.serverConfigs, baseline.serverConfigs) || current.toolsEnabled !== baseline.toolsEnabled || current.toolApprovalRequired !== baseline.toolApprovalRequired;
};

export { clearMcpToolChangeSurfaces, haveMcpFormValuesChanged, normalizeMcpConfigValues, syncMcpToolChangeSurfaces };
