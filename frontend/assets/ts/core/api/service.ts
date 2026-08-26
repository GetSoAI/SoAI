/* SoAI - Shared API service [frontend/assets/ts/core/api/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createConfigsEndpoints } from '@core/api/endpoints/configs.ts';
import { createFileExplorerEndpoints } from '@core/api/endpoints/fileExplorer.ts';
import { createFilesEndpoints } from '@core/api/endpoints/files.ts';
import { createHardwareEndpoints } from '@core/api/endpoints/hardware.ts';
import { createMcpEndpoints } from '@core/api/endpoints/mcp.ts';
import { createModelsEndpoints } from '@core/api/endpoints/models.ts';
import { createOpenAIEndpoints } from '@core/api/endpoints/openai.ts';
import { createPluginsEndpoints } from '@core/api/endpoints/plugins.ts';
import { createRoutingEndpoints } from '@core/api/endpoints/routing.ts';
import { createSoftwareEndpoints } from '@core/api/endpoints/software.ts';
import { createSystemEndpoints } from '@core/api/endpoints/system.ts';
import { createTasksEndpoints } from '@core/api/endpoints/tasks.ts';
import { createAutomationsEndpoints } from '@core/api/endpoints/automations.ts';
import { createWebuiEndpoints } from '@core/api/endpoints/webui.ts';
import { buildApiUrl, buildRelativeApiUrl, buildUploadFormData } from '@core/api/actions.ts';
import { executeApiRequest, fetchApiAsset } from '@core/api/effects.ts';
import { buildQueryRequestOptions } from '@core/api/requestOptions.ts';
import { encodeSegment } from '@core/identifiers.ts';
import { isFunction, isNullOrUndefined, isNumber, isString } from '@core/typeGuards.ts';
import type { ApiPathSegmentValue, ApiQueryParameters, ApiRequestBody, RequestOptions } from '@core/api/types/request.ts';
import { getDefaultHeaders } from '@core/api/constants.ts';
import { populateApiErrorDetail } from '@core/api/mappers.ts';
import { ApiRequestRuntime } from '@core/api/requestRuntime.ts';
import { ApiBaseUrlCoordinator } from '@core/api/baseUrlCoordinator.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeSearchResults, type SearchResultsResponse } from '@core/api/contracts/searchContracts.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { OsEndpoints } from '@core/api/endpoints/osEndpointContracts.ts';

class ApiClient {
    readonly os: OsEndpoints | null;
    constructor(createHostManagementApi: ((api: ApiClientContext) => OsEndpoints | null) | null = null) {
        this.os = createHostManagementApi === null ? null : createHostManagementApi(this);
    }
    #baseUrlCoordinator = new ApiBaseUrlCoordinator();
    readonly #requestRuntime = new ApiRequestRuntime({
        getBaseUrl: () => this.connectionState.getBaseUrl(),
        recoverFromNetworkFailure: (baseUrl) => this.#recoverFromNetworkFailure(baseUrl)
    });
    #networkRecoveryBase: string | null = null;
    #networkRecoveryGeneration = 0;
    #networkRecoveryPromise: Promise<void> | null = null;
    #authTransitionGate: (() => Promise<void>) | null = null;
    defaultHeaders: Record<string, string> = { ...getDefaultHeaders() };
    initialize = (): Promise<string> => this.ensureBaseUrl({ allowDiscovery: true });
    ensureBaseUrl = (options: { allowDiscovery?: boolean } = {}): Promise<string> => this.#baseUrlCoordinator.ensureBaseUrl(options);
    whenReady = (options: { allowDiscovery?: boolean; signal?: AbortSignal } = {}): Promise<string> => this.#baseUrlCoordinator.whenReady(options);
    discoverAndSetBaseUrl = (): Promise<string> => this.#baseUrlCoordinator.discoverAndSetBaseUrl();
    onReady = (listener: (baseUrl: string | null) => void, options: { immediate?: boolean; ensure?: boolean; allowDiscovery?: boolean } = {}): (() => void) => {
        if (!isFunction(listener)) {
            throw new Error('Ready listener must be a function');
        }
        return this.#baseUrlCoordinator.onReady(listener, options);
    };
    setBaseUrl = (baseUrl: string | null | undefined): void => {
        this.#baseUrlCoordinator.setBaseUrl(baseUrl);
    };
    clearBaseUrl = (): void => {
        this.#baseUrlCoordinator.clearBaseUrl();
    };
    onBaseUrlChange = (listener: (baseUrl: string | null) => void): (() => void) => {
        if (!isFunction(listener)) {
            throw new Error('Base URL listener must be a function');
        }
        return this.#baseUrlCoordinator.onBaseUrlChange(listener);
    };
    getBaseUrl = (): string | null => this.#baseUrlCoordinator.getBaseUrl();
    hasBaseUrl = (): boolean => this.#baseUrlCoordinator.hasBaseUrl();
    encodePathSegment = (value: ApiPathSegmentValue): string => {
        if (isString(value)) {
            return encodeSegment(value.trim());
        }
        if (isNumber(value) && Number.isFinite(value)) {
            return encodeSegment(String(value));
        }
        return '';
    };
    buildRelativeUrl = (endpoint: string, query: ApiQueryParameters | null = null): string => buildRelativeApiUrl(endpoint, query);
    buildUrl = (endpoint: string, query: ApiQueryParameters | null = null): string => buildApiUrl(endpoint, query, this.connectionState.getBaseUrl() || null);
    request = async (method: string, endpoint: string, data: ApiRequestBody = undefined, options: RequestOptions = {}): Promise<ApiResponsePayload> => {
        const normalizedMethod = method.toUpperCase();
        const protectedRead = normalizedMethod === 'GET' || (normalizedMethod === 'POST' && endpoint.includes('/users/mutations/') && endpoint.endsWith('/status'));
        if (protectedRead && endpoint.startsWith('/api/') && options.authTransitionOwned !== true && this.#authTransitionGate !== null) {
            await this.#authTransitionGate();
        }
        return executeApiRequest(method, endpoint, data, options, {
            defaultHeaders: this.defaultHeaders,
            whenReady: (readyOptions) => this.whenReady(readyOptions),
            buildUrl: (targetEndpoint, targetQuery) => this.buildUrl(targetEndpoint, targetQuery),
            getBaseUrl: () => this.connectionState.getBaseUrl(),
            resetNetworkErrorState: this.#requestRuntime.resetNetworkErrorState,
            registerNetworkError: this.#requestRuntime.registerNetworkError,
            handleAuthenticationError: this.#requestRuntime.handleAuthenticationError,
            populateApiErrorDetail
        });
    };
    setAuthTransitionGate = (gate: (() => Promise<void>) | null): void => {
        this.#authTransitionGate = gate;
    };
    #recoverFromNetworkFailure(baseUrl: string): void {
        if (this.#networkRecoveryPromise && this.#networkRecoveryBase === baseUrl) {
            return;
        }
        this.#networkRecoveryGeneration += 1;
        const recoveryGeneration = this.#networkRecoveryGeneration;
        this.#networkRecoveryBase = baseUrl;
        const recoveryPromise = (async (): Promise<void> => {
            const healthy = await this.#baseUrlCoordinator.revalidateBaseUrl(baseUrl);
            if (this.#networkRecoveryGeneration !== recoveryGeneration) {
                return;
            }
            if (this.connectionState.getBaseUrl() !== baseUrl) {
                return;
            }
            if (healthy) {
                return;
            }
            this.connectionState.clearBaseUrl({ releaseConfigured: false });
            this.#baseUrlCoordinator.discoveryComplete = false;
            this.#baseUrlCoordinator.initialized = false;
            await this.#baseUrlCoordinator.recoverBaseUrl({
                allowDiscovery: true,
                shouldContinue: () => this.#networkRecoveryGeneration === recoveryGeneration
            });
        })()
            .catch((error) => {
                errorHandler.warn('ApiClient', 'Automatic discovery after network failure failed', ensureError(error));
            })
            .finally(() => {
                if (this.#networkRecoveryPromise === recoveryPromise && this.#networkRecoveryGeneration === recoveryGeneration) {
                    this.#networkRecoveryBase = null;
                    this.#networkRecoveryPromise = null;
                }
            });
        this.#networkRecoveryPromise = recoveryPromise;
    }
    get = (endpoint: string, options: RequestOptions = {}): Promise<ApiResponsePayload> => this.request('GET', endpoint, undefined, options);
    post = (endpoint: string, data?: ApiRequestBody, options: RequestOptions = {}): Promise<ApiResponsePayload> => this.request('POST', endpoint, data, options);
    put = (endpoint: string, data?: ApiRequestBody, options: RequestOptions = {}): Promise<ApiResponsePayload> => this.request('PUT', endpoint, data, options);
    patch = (endpoint: string, data?: ApiRequestBody, options: RequestOptions = {}): Promise<ApiResponsePayload> => this.request('PATCH', endpoint, data, options);
    delete = (endpoint: string, options: RequestOptions = {}): Promise<ApiResponsePayload> => this.request('DELETE', endpoint, undefined, options);
    uploadFile = (endpoint: string, file: Blob, additionalData: Record<string, string | Blob> = {}, options: RequestOptions = {}, filenameOverride: string | null = null): Promise<ApiResponsePayload> => this.post(endpoint, buildUploadFormData(file, additionalData, filenameOverride), { ...options, headers: {} });
    fetchAsset = (path: string, options: { timeout?: number; responseType?: 'text' | 'json' | 'blob'; signal?: AbortSignal } = {}): Promise<ApiResponsePayload> => fetchApiAsset(path, options);
    search = async (query: string, limit: number = 20, options: { signal?: AbortSignal | null | undefined } = {}): Promise<SearchResultsResponse> => {
        return decodeSearchResults(await this.get('/api/v1/search', buildQueryRequestOptions({ q: query, limit }, options.signal)));
    };
    reset = (): void => {
        this.#requestRuntime.resetNetworkErrorState();
        this.#networkRecoveryGeneration += 1;
        this.#networkRecoveryBase = null;
        this.#networkRecoveryPromise = null;
        this.#baseUrlCoordinator.reset();
        this.#authTransitionGate = null;
        this.defaultHeaders = { ...getDefaultHeaders() };
    };
    system = createSystemEndpoints(this);
    tasks = createTasksEndpoints(this);
    configs = createConfigsEndpoints(this);
    automations = createAutomationsEndpoints(this);
    webui = createWebuiEndpoints(this);
    mcp = createMcpEndpoints(this);
    routing = createRoutingEndpoints(this);
    software = createSoftwareEndpoints(this);
    models = createModelsEndpoints(this);
    plugins = createPluginsEndpoints(this);
    hardware = createHardwareEndpoints(this);
    files = createFilesEndpoints(this);
    fileExplorer = createFileExplorerEndpoints(this);
    openai = createOpenAIEndpoints(this);
    get baseUrl(): string | null {
        return this.getBaseUrl();
    }
    set baseUrl(value: string | null | undefined | void) {
        if (isNullOrUndefined(value) || value === '') {
            this.clearBaseUrl();
            return;
        }
        if (!isString(value) || !value.trim()) {
            throw new Error('ApiClient baseUrl must be a non-empty string');
        }
        this.setBaseUrl(value);
    }
    get connectionState() {
        return this.#baseUrlCoordinator.connectionState;
    }
}
export { ApiClient };
const getApiClient = (): ApiClient => {
    const candidate = resolveKernelService('core.apiClient');
    if (!(candidate instanceof ApiClient)) {
        throw new Error('core.apiClient is not registered');
    }
    return candidate;
};
const resetApiClient = (): void => {
    getApiClient().reset();
};
export { getApiClient, resetApiClient };
