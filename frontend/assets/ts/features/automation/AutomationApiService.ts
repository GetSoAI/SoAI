/* SoAI - Frontend automation API service [frontend/assets/ts/features/automation/AutomationApiService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { AsyncOnceGuard } from '@core/concurrency/AsyncOnce.ts';
import type { ApiClient } from '@core/api/service.ts';
import { resolveWorkspaceBrowserAccess } from '@core/fileexplorerbrowser/workspaceBrowserAccess.ts';
import { parseAutomationModelOptions } from '@features/automation/modelOptions.ts';
import type { AutomationDataService, AutomationDefinitionResponse, AutomationDefinitionsPageResponse, AutomationMcpCatalogResponse, AutomationModelOption, AutomationOccurrenceKeyRequest, AutomationOccurrencesDeleteResponse, AutomationOccurrencesPageResponse, AutomationRunResponse, AutomationSchedulePreviewRequest, AutomationSchedulePreviewResponse, AutomationWorkspaceAccess, CreateAutomationRequest, UpdateAutomationRequest } from '@features/automation/contracts.ts';

type AutomationApiClient = {
    automations: Pick<ApiClient['automations'], 'create' | 'delete' | 'get' | 'list' | 'occurrences' | 'occurrencesDelete' | 'runNow' | 'schedulePreview' | 'update'> & {
        mcp: Pick<ApiClient['automations']['mcp'], 'tools'>;
        runs: Pick<ApiClient['automations']['runs'], 'get'>;
    };
    fileExplorer: Pick<ApiClient['fileExplorer'], 'list' | 'search'>;
    models: Pick<ApiClient['models'], 'list'>;
    webui: {
        auth: Pick<ApiClient['webui']['auth'], 'getMe'>;
    };
};

class AutomationApiService implements AutomationDataService {
    readonly #api: AutomationApiClient;
    #mcpCatalogOnce = new AsyncOnceGuard<AutomationMcpCatalogResponse>();

    #catalogScope: AbortSignal | null = null;

    constructor(api: AutomationApiClient) {
        this.#api = api;
    }

    async listAutomations(limit: number, offset: number, signal?: AbortSignal): Promise<AutomationDefinitionsPageResponse> {
        return await this.#api.automations.list({ limit, offset, ...(signal ? { signal } : {}) });
    }

    async getZonesWindow(fromUtcMs: number, toUtcMs: number, offset: number, signal?: AbortSignal): Promise<AutomationOccurrencesPageResponse> {
        return await this.#api.automations.occurrences(fromUtcMs, toUtcMs, offset, signal);
    }

    async listAvailableModels(signal?: AbortSignal): Promise<readonly AutomationModelOption[]> {
        return parseAutomationModelOptions(await this.#api.models.list({ signal }));
    }

    async getMcpCatalog(options: { signal?: AbortSignal | undefined; refresh?: boolean } = {}): Promise<AutomationMcpCatalogResponse> {
        const signal = options.signal;
        throwIfAborted(signal);
        if (!signal) return await this.#api.automations.mcp.tools();
        if (this.#catalogScope !== signal || options.refresh === true) {
            this.#catalogScope = signal;
            this.#mcpCatalogOnce = new AsyncOnceGuard<AutomationMcpCatalogResponse>();
        }
        return await raceWithAbortSignal(
            this.#mcpCatalogOnce.run(() => this.#api.automations.mcp.tools(signal)),
            signal
        );
    }

    async getWorkspaceAccess(signal?: AbortSignal): Promise<AutomationWorkspaceAccess> {
        return await resolveWorkspaceBrowserAccess({
            getCurrentUser: () => this.#api.webui.auth.getMe({ signal }),
            scopedBrowserApi: this.#api.fileExplorer
        });
    }

    async getAutomation(automationId: string, signal?: AbortSignal): Promise<AutomationDefinitionResponse> {
        return await this.#api.automations.get(automationId, signal);
    }

    async previewSchedule(input: AutomationSchedulePreviewRequest, signal?: AbortSignal): Promise<AutomationSchedulePreviewResponse> {
        return await this.#api.automations.schedulePreview(input, signal);
    }

    async createAutomation(payload: CreateAutomationRequest): Promise<AutomationDefinitionResponse> {
        return await this.#api.automations.create(payload);
    }

    async updateAutomation(automationId: string, payload: UpdateAutomationRequest, expectedRevision: string | null): Promise<AutomationDefinitionResponse> {
        return await this.#api.automations.update(automationId, payload, { expectedRevision });
    }

    async runAutomationNow(automationId: string): Promise<AutomationRunResponse> {
        return await this.#api.automations.runNow(automationId);
    }

    async getRun(runId: string, signal?: AbortSignal): Promise<AutomationRunResponse> {
        return await this.#api.automations.runs.get(runId, signal);
    }

    async deleteAutomation(automationId: string): Promise<void> {
        await this.#api.automations.delete(automationId);
    }

    async deleteOccurrences(occurrences: readonly AutomationOccurrenceKeyRequest[]): Promise<AutomationOccurrencesDeleteResponse> {
        return await this.#api.automations.occurrencesDelete({ occurrences });
    }
}

export { AutomationApiService };
export type { AutomationApiClient };
