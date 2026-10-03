/* SoAI - Frontend automation data contracts [frontend/assets/ts/features/automation/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationDefinitionResponse, AutomationDefinitionsPageResponse, AutomationMcpCatalogResponse, AutomationOccurrenceKeyRequest, AutomationOccurrencesDeleteResponse, AutomationOccurrencesPageResponse, AutomationRunResponse, AutomationSchedulePreviewRequest, AutomationSchedulePreviewResponse, CreateAutomationRequest, UpdateAutomationRequest } from '@core/api/contracts/automationContractTypes.ts';
import type { ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import type { ChatExecutionIneligibilityReason } from '@core/models/chatExecutionEligibility.ts';

interface AutomationModelOption {
    id: string;
    detailUniversalId: string | null;
    label: string;
    provider: string | null;
    loaded: boolean;
    available: boolean;
    ineligibleReason: ChatExecutionIneligibilityReason | null;
}

interface AutomationWorkspaceAccess {
    currentWorkspacePath: string;
    browserApi: ReadOnlyFileBrowserApi;
}

interface AutomationDataService {
    listAutomations(limit: number, offset: number, signal?: AbortSignal): Promise<AutomationDefinitionsPageResponse>;
    getZonesWindow(fromUtcMs: number, toUtcMs: number, offset: number, signal?: AbortSignal): Promise<AutomationOccurrencesPageResponse>;
    listAvailableModels(signal?: AbortSignal): Promise<readonly AutomationModelOption[]>;
    getMcpCatalog(options?: { signal?: AbortSignal | undefined; refresh?: boolean }): Promise<AutomationMcpCatalogResponse>;
    getWorkspaceAccess(signal?: AbortSignal): Promise<AutomationWorkspaceAccess>;
    getAutomation(automationId: string, signal?: AbortSignal): Promise<AutomationDefinitionResponse>;
    previewSchedule(input: AutomationSchedulePreviewRequest, signal?: AbortSignal): Promise<AutomationSchedulePreviewResponse>;
    createAutomation(payload: CreateAutomationRequest): Promise<AutomationDefinitionResponse>;
    updateAutomation(automationId: string, payload: UpdateAutomationRequest, expectedRevision: string | null): Promise<AutomationDefinitionResponse>;
    runAutomationNow(automationId: string): Promise<AutomationRunResponse>;
    getRun(runId: string, signal?: AbortSignal): Promise<AutomationRunResponse>;
    deleteAutomation(automationId: string): Promise<void>;
    deleteOccurrences(occurrences: readonly AutomationOccurrenceKeyRequest[]): Promise<AutomationOccurrencesDeleteResponse>;
}

export type { AutomationColor, AutomationDefinitionResponse, AutomationDefinitionsPageResponse, AutomationLatestRunResponse, AutomationMcpCatalogResponse, AutomationModelSettings, AutomationOccurrenceKeyRequest, AutomationOccurrenceResponse, AutomationOccurrencesDeleteResponse, AutomationOccurrencesPageResponse, AutomationRunResponse, AutomationSchedulePreviewRequest, AutomationSchedulePreviewResponse, CreateAutomationRequest, UpdateAutomationRequest } from '@core/api/contracts/automationContractTypes.ts';
export type { AutomationDataService, AutomationModelOption, AutomationWorkspaceAccess };
