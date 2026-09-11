/* SoAI - Frontend automation data contracts [frontend/assets/ts/features/automation/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationModelSettings } from '@core/api/contracts/automationContractTypes.ts';
import type { AutomationRecurrence, AutomationRunStatus, AutomationZoneStatus } from '@core/automation/protocols.ts';
import type { ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import type { McpTool } from '@core/mcp/configTypes.ts';

type AutomationColor = 'Red' | 'Yellow' | 'Purple' | 'Green' | 'Blue' | null;

interface AutomationDefinition {
    id: string;
    title: string;
    enabled: boolean;
    interactiveToolApproval: boolean;
    color: AutomationColor;
    timezone: string;
    startLocal: string;
    recurrence: AutomationRecurrence;
    turns: readonly string[];
    maxTurns: number;
    maxTurnChars: number;
    maxRunMinutes: number;
    modelSettings: AutomationModelSettings;
    nextRunAtMs: number | null;
    createdAtMs: number;
    lastModifiedAtMs: number;
}

interface AutomationZone {
    automationId: string;
    scheduledAtMs: number;
    title: string;
    enabled: boolean | null;
    color: AutomationColor;
    runId: string | null;
    status: AutomationZoneStatus;
    resultExcerpt: string | null;
    statusMessage: string | null;
    convId: string | null;
    startedAtActualMs: number | null;
    finishedAtMs: number | null;
}

interface AutomationRunRecord {
    runId: string;
    automationId: string;
    scheduledAtMs: number;
    startedAtActualMs: number | null;
    finishedAtMs: number | null;
    status: AutomationRunStatus;
    statusMessage: string | null;
    resultExcerpt: string | null;
    convId: string | null;
    title: string | null;
    enabled: boolean | null;
    color: AutomationColor;
}

interface AutomationOccurrenceKey {
    automationId: string;
    scheduledAtMs: number;
}

interface AutomationOccurrencesDeleteResult {
    deletedOccurrenceCount: number;
    deletedRunCount: number;
    cancelledRunIds: readonly string[];
}

interface AutomationDefinitionsPage {
    automations: readonly AutomationDefinition[];
    hasMore: boolean;
    nextOffset: number | null;
    limit: number;
    offset: number;
}

interface AutomationOccurrencesWindowPage {
    occurrences: readonly AutomationZone[];
    limit: number;
    offset: number;
    hasMore: boolean;
    nextOffset: number | null;
}

interface AutomationModelOption {
    id: string;
    detailUniversalId: string | null;
    label: string;
    provider: string | null;
    loaded: boolean;
    available: boolean;
}

interface AutomationMcpCatalog {
    tools: readonly McpTool[];
    defaultTools: readonly string[];
    planTools: readonly string[];
    executeTools: readonly string[];
}

interface AutomationWorkspaceAccess {
    currentWorkspacePath: string;
    browserApi: ReadOnlyFileBrowserApi;
}

interface CreateAutomationPayload {
    title: string;
    enabled: boolean;
    interactiveToolApproval: boolean;
    color: AutomationColor;
    timezone: string;
    startLocal: string;
    recurrence: AutomationRecurrence;
    turns: readonly string[];
    maxTurns: number;
    maxTurnChars: number;
    maxRunMinutes: number;
    modelSettings: AutomationDefinition['modelSettings'];
}

interface UpdateAutomationPayload {
    title?: string;
    enabled?: boolean;
    interactiveToolApproval?: boolean;
    color?: AutomationColor;
    timezone?: string;
    startLocal?: string;
    recurrence?: AutomationRecurrence;
    turns?: readonly string[];
    maxTurns?: number;
    maxTurnChars?: number;
    maxRunMinutes?: number;
    modelSettings?: AutomationDefinition['modelSettings'];
}

interface AutomationDataService {
    listAutomations(limit: number, offset: number): Promise<AutomationDefinitionsPage>;
    getZonesWindow(fromUtcMs: number, toUtcMs: number, offset: number): Promise<AutomationOccurrencesWindowPage>;
    listAvailableModels(): Promise<readonly AutomationModelOption[]>;
    getMcpCatalog(): Promise<AutomationMcpCatalog>;
    getWorkspaceAccess(): Promise<AutomationWorkspaceAccess>;
    createAutomation(payload: CreateAutomationPayload): Promise<AutomationDefinition>;
    updateAutomation(automationId: string, payload: UpdateAutomationPayload): Promise<AutomationDefinition>;
    runAutomationNow(automationId: string): Promise<AutomationRunRecord>;
    getRun(runId: string): Promise<AutomationRunRecord>;
    deleteAutomation(automationId: string): Promise<void>;
    deleteOccurrences(occurrences: readonly AutomationOccurrenceKey[]): Promise<AutomationOccurrencesDeleteResult>;
}

export type { AutomationColor, AutomationDataService, AutomationDefinition, AutomationDefinitionsPage, AutomationMcpCatalog, AutomationModelOption, AutomationOccurrenceKey, AutomationOccurrencesDeleteResult, AutomationOccurrencesWindowPage, AutomationRunRecord, AutomationWorkspaceAccess, AutomationZone, CreateAutomationPayload, UpdateAutomationPayload };
