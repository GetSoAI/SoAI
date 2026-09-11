/* SoAI - Frontend automation API service [frontend/assets/ts/features/automation/AutomationApiService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AsyncOnceGuard } from '@core/concurrency/AsyncOnce.ts';
import type { ModelCatalogResponse } from '@core/api/contracts/modelCatalogContracts.ts';
import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import type { HostFilesystemBrowserApi, ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import { resolveWorkspaceBrowserAccess } from '@core/fileexplorerbrowser/workspaceBrowserAccess.ts';
import { parseAutomationModelOptions } from '@features/automation/modelOptions.ts';
import type { AutomationDataService, AutomationDefinition, AutomationDefinitionsPage, AutomationMcpCatalog, AutomationModelOption, AutomationOccurrenceKey, AutomationOccurrencesDeleteResult, AutomationOccurrencesWindowPage, AutomationRunRecord, AutomationWorkspaceAccess, CreateAutomationPayload, UpdateAutomationPayload } from '@features/automation/contracts.ts';

interface AutomationApiClient {
    automations: {
        list(options?: { limit?: number; offset?: number }): Promise<AutomationDefinitionsPage>;
        occurrences(fromUtcMs: number, toUtcMs: number, offset: number): Promise<AutomationOccurrencesWindowPage>;
        occurrencesDelete(payload: { occurrences: readonly AutomationOccurrenceKey[] }): Promise<AutomationOccurrencesDeleteResult>;
        create(payload: CreateAutomationPayload): Promise<AutomationDefinition>;
        update(automationId: string, payload: UpdateAutomationPayload): Promise<AutomationDefinition>;
        delete(automationId: string): Promise<void>;
        runNow(automationId: string): Promise<AutomationRunRecord>;
        runs: {
            get(runId: string): Promise<AutomationRunRecord>;
        };
        mcp: {
            tools(): Promise<AutomationMcpCatalog>;
        };
    };
    models: {
        list(): Promise<ModelCatalogResponse>;
    };
    webui: {
        auth: {
            getMe(): Promise<WebuiUser>;
        };
        users: {
            workspaceBrowser: HostFilesystemBrowserApi;
        };
    };
    fileExplorer: ReadOnlyFileBrowserApi;
}

class AutomationApiService implements AutomationDataService {
    readonly #api: AutomationApiClient;
    readonly #mcpCatalogOnce = new AsyncOnceGuard<AutomationMcpCatalog>();

    constructor(api: AutomationApiClient) {
        this.#api = api;
    }

    async listAutomations(limit: number, offset: number): Promise<AutomationDefinitionsPage> {
        return await this.#api.automations.list({ limit, offset });
    }

    async getZonesWindow(fromUtcMs: number, toUtcMs: number, offset: number): Promise<AutomationOccurrencesWindowPage> {
        return await this.#api.automations.occurrences(fromUtcMs, toUtcMs, offset);
    }

    async listAvailableModels(): Promise<readonly AutomationModelOption[]> {
        return parseAutomationModelOptions(await this.#api.models.list());
    }

    async getMcpCatalog(): Promise<AutomationMcpCatalog> {
        return this.#mcpCatalogOnce.run(async () => await this.#api.automations.mcp.tools());
    }

    async getWorkspaceAccess(): Promise<AutomationWorkspaceAccess> {
        return await resolveWorkspaceBrowserAccess({
            getCurrentUser: () => this.#api.webui.auth.getMe(),
            scopedBrowserApi: this.#api.fileExplorer
        });
    }

    async createAutomation(payload: CreateAutomationPayload): Promise<AutomationDefinition> {
        return await this.#api.automations.create(payload);
    }

    async updateAutomation(automationId: string, payload: UpdateAutomationPayload): Promise<AutomationDefinition> {
        return await this.#api.automations.update(automationId, payload);
    }

    async runAutomationNow(automationId: string): Promise<AutomationRunRecord> {
        return await this.#api.automations.runNow(automationId);
    }

    async getRun(runId: string): Promise<AutomationRunRecord> {
        return await this.#api.automations.runs.get(runId);
    }

    async deleteAutomation(automationId: string): Promise<void> {
        await this.#api.automations.delete(automationId);
    }

    async deleteOccurrences(occurrences: readonly AutomationOccurrenceKey[]): Promise<AutomationOccurrencesDeleteResult> {
        return await this.#api.automations.occurrencesDelete({ occurrences });
    }
}

export { AutomationApiService };
export type { AutomationApiClient };
