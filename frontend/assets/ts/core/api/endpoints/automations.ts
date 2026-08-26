/* SoAI - Shared API automations [frontend/assets/ts/core/api/endpoints/automations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeAutomationDefinition, decodeAutomationDefinitionList, decodeAutomationMcpCatalog, decodeAutomationOccurrenceList, decodeAutomationOccurrencesDeleteResult, decodeAutomationRun, decodeAutomationRunList } from '@core/api/contracts/automationContracts.ts';
import type { AutomationDefinitionResponse, AutomationDefinitionsPageResponse, AutomationMcpCatalogResponse, AutomationOccurrenceKeyRequest, AutomationOccurrencesDeleteResponse, AutomationOccurrencesPageResponse, AutomationRunResponse, CreateAutomationRequest, UpdateAutomationRequest } from '@core/api/contracts/automationContractTypes.ts';
import { serializeAutomationOccurrenceKey, serializeCreateAutomationRequest, serializeUpdateAutomationRequest } from '@core/api/contracts/automationRequestSerialization.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';

const createAutomationsEndpoints = (
    api: ApiClientContext
): {
    list: (options?: { limit?: number; offset?: number }) => Promise<AutomationDefinitionsPageResponse>;
    create: (payload: CreateAutomationRequest) => Promise<AutomationDefinitionResponse>;
    get: (automationId: string) => Promise<AutomationDefinitionResponse>;
    update: (automationId: string, payload: UpdateAutomationRequest) => Promise<AutomationDefinitionResponse>;
    delete: (automationId: string) => Promise<void>;
    runNow: (automationId: string) => Promise<AutomationRunResponse>;
    occurrences: (fromUtcMs: number, toUtcMs: number, offset: number) => Promise<AutomationOccurrencesPageResponse>;
    occurrencesDelete: (payload: { occurrences: readonly AutomationOccurrenceKeyRequest[] }) => Promise<AutomationOccurrencesDeleteResponse>;
    runs: { listActive: () => Promise<readonly AutomationRunResponse[]>; list: (options: { fromUtcMs: number; toUtcMs: number; automationId?: string; limit?: number; offset?: number }) => Promise<readonly AutomationRunResponse[]>; get: (runId: string) => Promise<AutomationRunResponse> };
    mcp: { tools: () => Promise<AutomationMcpCatalogResponse> };
} => ({
    list: async (options?: { limit?: number; offset?: number }): Promise<AutomationDefinitionsPageResponse> => decodeAutomationDefinitionList(await api.get('/api/v1/automations', options === undefined ? {} : { query: options })),
    create: async (payload: CreateAutomationRequest): Promise<AutomationDefinitionResponse> => decodeAutomationDefinition(await api.post('/api/v1/automations', serializeCreateAutomationRequest(payload)), 'Automation create'),
    get: async (automationId: string): Promise<AutomationDefinitionResponse> => decodeAutomationDefinition(await api.get(`/api/v1/automations/${api.encodePathSegment(automationId)}`), 'Automation get'),
    update: async (automationId: string, payload: UpdateAutomationRequest): Promise<AutomationDefinitionResponse> => decodeAutomationDefinition(await api.patch(`/api/v1/automations/${api.encodePathSegment(automationId)}`, serializeUpdateAutomationRequest(payload)), 'Automation update'),
    delete: async (automationId: string): Promise<void> => {
        decodeNoContentResponse(await api.delete(`/api/v1/automations/${api.encodePathSegment(automationId)}`), 'Automation delete response');
    },
    runNow: async (automationId: string): Promise<AutomationRunResponse> => decodeAutomationRun(await api.post(`/api/v1/automations/${api.encodePathSegment(automationId)}/run-now`), 'Automation run now'),
    occurrences: async (fromUtcMs: number, toUtcMs: number, offset: number): Promise<AutomationOccurrencesPageResponse> => decodeAutomationOccurrenceList(await api.get('/api/v1/automations/occurrences', { query: { 'from_utc_ms': fromUtcMs, 'to_utc_ms': toUtcMs, offset } })),
    occurrencesDelete: async (payload: { occurrences: readonly AutomationOccurrenceKeyRequest[] }): Promise<AutomationOccurrencesDeleteResponse> => decodeAutomationOccurrencesDeleteResult(await api.post('/api/v1/automations/occurrences/delete', { occurrences: payload.occurrences.map(serializeAutomationOccurrenceKey) })),
    runs: {
        listActive: async (): Promise<readonly AutomationRunResponse[]> => decodeAutomationRunList(await api.get('/api/v1/automations/runs/active'), 'Active automation runs'),
        list: async (options: { fromUtcMs: number; toUtcMs: number; automationId?: string; limit?: number; offset?: number }): Promise<readonly AutomationRunResponse[]> => decodeAutomationRunList(await api.get('/api/v1/automations/runs', { query: { 'from_utc_ms': options.fromUtcMs, 'to_utc_ms': options.toUtcMs, 'automation_id': options.automationId, limit: options.limit, offset: options.offset } }), 'Automation runs'),
        get: async (runId: string): Promise<AutomationRunResponse> => decodeAutomationRun(await api.get(`/api/v1/automations/runs/${api.encodePathSegment(runId)}`), 'Automation run')
    },
    mcp: {
        tools: async (): Promise<AutomationMcpCatalogResponse> => decodeAutomationMcpCatalog(await api.get('/api/v1/automations/mcp/tools'))
    }
});

export { createAutomationsEndpoints };
