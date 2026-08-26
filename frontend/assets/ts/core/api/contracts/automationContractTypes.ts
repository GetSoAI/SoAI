/* SoAI - Automation API payload type declarations [frontend/assets/ts/core/api/contracts/automationContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationRecurrence, AutomationRunStatus, AutomationZoneStatus } from '@core/automation/protocols.ts';
import type { McpFormValues, McpTool } from '@core/mcp/configTypes.ts';
import type { ChatRequestParameters } from '@core/types/chatParameters.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

type AutomationColor = 'Red' | 'Yellow' | 'Purple' | 'Green' | 'Blue' | null;

type AutomationModelSettings = Partial<ChatRequestParameters> & {
    model: string;
    agent: { mode: 'execute'; maxIterations?: number };
    mcp: McpFormValues;
    workspacePath?: string | null;
    prompts?: {
        userSystemPrompt?: string | null;
        userSystemPromptLockEnabled?: boolean;
        soaiSystemPromptEnabled?: boolean;
        additionalPrompts?: JsonObject;
    };
    temperature?: number | null;
    topP?: number | null;
    seed?: number | null;
};

interface AutomationDefinitionResponse {
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

interface AutomationOccurrenceResponse {
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

interface AutomationRunResponse {
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

interface AutomationOccurrenceKeyRequest {
    automationId: string;
    scheduledAtMs: number;
}

interface AutomationOccurrencesDeleteResponse {
    deletedOccurrenceCount: number;
    deletedRunCount: number;
    cancelledRunIds: readonly string[];
}

interface AutomationDefinitionsPageResponse {
    automations: readonly AutomationDefinitionResponse[];
    hasMore: boolean;
    nextOffset: number | null;
    limit: number;
    offset: number;
}

interface AutomationOccurrencesPageResponse {
    occurrences: readonly AutomationOccurrenceResponse[];
    limit: number;
    offset: number;
    hasMore: boolean;
    nextOffset: number | null;
}

interface AutomationMcpCatalogResponse {
    tools: readonly McpTool[];
    defaultTools: readonly string[];
    planTools: readonly string[];
    executeTools: readonly string[];
}

interface CreateAutomationRequest {
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
}

interface UpdateAutomationRequest {
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
    modelSettings?: AutomationModelSettings;
}

export type { AutomationColor, AutomationDefinitionResponse, AutomationDefinitionsPageResponse, AutomationMcpCatalogResponse, AutomationModelSettings, AutomationOccurrenceKeyRequest, AutomationOccurrenceResponse, AutomationOccurrencesDeleteResponse, AutomationOccurrencesPageResponse, AutomationRunResponse, CreateAutomationRequest, UpdateAutomationRequest };
