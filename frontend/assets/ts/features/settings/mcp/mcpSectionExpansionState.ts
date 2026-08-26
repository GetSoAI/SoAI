/* SoAI - MCP settings section expansion persistence [frontend/assets/ts/features/settings/mcp/mcpSectionExpansionState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readStorageJson, writeStorageJson } from '@core/storage/ttlStorageCache.ts';
import { isBoolean, isPlainObject } from '@core/typeGuards.ts';

const MCP_SECTION_EXPANSION_STORAGE_KEY = 'soai.settings.mcp.sectionExpansion';

type McpSectionExpansionResolver = (sectionId: string, fallbackExpanded: boolean) => boolean;

interface McpSectionExpansionState {
    resolve: McpSectionExpansionResolver;
    set: (sectionId: string, expanded: boolean) => void;
}

const readStoredExpansion = (): Map<string, boolean> => {
    const stored = readStorageJson('localStorage', MCP_SECTION_EXPANSION_STORAGE_KEY);
    const expansion = new Map<string, boolean>();
    if (!isPlainObject(stored)) {
        return expansion;
    }
    for (const [sectionId, expanded] of Object.entries(stored)) {
        if (isBoolean(expanded)) {
            expansion.set(sectionId, expanded);
        }
    }
    return expansion;
};

const writeStoredExpansion = (expansion: Map<string, boolean>): void => {
    const payload: Record<string, boolean> = {};
    for (const sectionId of Array.from(expansion.keys()).sort((left, right) => left.localeCompare(right, 'en'))) {
        const expanded = expansion.get(sectionId);
        if (expanded !== undefined) {
            payload[sectionId] = expanded;
        }
    }
    writeStorageJson('localStorage', MCP_SECTION_EXPANSION_STORAGE_KEY, payload);
};

const createMcpSectionExpansionState = (): McpSectionExpansionState => {
    const expansion = readStoredExpansion();
    return {
        resolve(sectionId: string, fallbackExpanded: boolean): boolean {
            return expansion.get(sectionId) ?? fallbackExpanded;
        },
        set(sectionId: string, expanded: boolean): void {
            expansion.set(sectionId, expanded);
            writeStoredExpansion(expansion);
        }
    };
};

export { createMcpSectionExpansionState };
export type { McpSectionExpansionResolver, McpSectionExpansionState };
