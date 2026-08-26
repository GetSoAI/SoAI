/* SoAI - Models feature download modal types [frontend/assets/ts/features/models/modals/downloadmodal/downloadModalTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ExternalProviderCreateResponse } from '@core/api/contracts/pluginProviderContracts.ts';
import type { RemoteModelSearchResult } from '@core/api/contracts/pluginSearchContracts.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { EnsureCollectionStreamOptions, StreamActionHandle, StreamHandle } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { SetButtonLoadingOptions } from '@core/state/UIStateManager.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { SanitizerApi } from '@core/pagecontext/contracts.ts';
import type { ModelDiscoveryResponse } from '@core/api/contracts/modelOperationContracts.ts';
import type { ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import type { ManualInstallPathResponse } from '@core/api/contracts/manualInstallPathContracts.ts';

type Sanitizer = Pick<SanitizerApi, 'attribute' | 'html'>;

interface ProviderAddPayload {
    name?: string;
    apiUrl: string;
    apiKey?: string;
    modelsFilter?: string[];
}

interface DownloadModalApi {
    models: {
        discover(): Promise<ModelDiscoveryResponse>;
        manualInstall(): Promise<ManualInstallPathResponse>;
    };
    plugins: {
        providers: {
            add(pluginName: string, payload: ProviderAddPayload): Promise<ExternalProviderCreateResponse>;
        };
    };
}

interface ClipboardApi {
    isSupported(): boolean;
}

interface CopyToClipboardOptions {
    notify?: (message: string, type: NotificationType) => void;
}

interface VariantProbeController {
    reset(): void;
    enableVariantFilter(): void;
    applyVariantFilter(): void;
    updateButtonState(): void;
    prepareForProbe(): symbol;
    showCheckingStatus(): void;
    isTokenActive(candidate: symbol): boolean;
    handleSuccess(token: symbol, variants: ModelVariantResponse[]): void;
    buildErrorMessage(error: Error): string | null;
    handleFailure(token: symbol, message: string): void;
    handleEntryClick(event: Event | null, element: Element | null): boolean;
    handleEntryKeydown(event: KeyboardEvent | null, element: Element | null): boolean;
}

interface StreamTracker {
    track: (key: string, handle: StreamHandle) => void;
    release: (key: string) => void;
    active?: Map<string, StreamHandle>;
    size?: number;
}

interface StreamManagerContract {
    ensureResourceStarted?: (key: string) => Promise<JsonValue | null | undefined>;
    refresh: (resource: string, options?: EnsureCollectionStreamOptions) => Promise<JsonValue | null | undefined>;
    hasActiveOperationsOfType: (type: string) => boolean;
}

interface ModelActions {
    searchRemoteModels(plugin: string, query: string, options?: { limit?: number; signal?: AbortSignal }): Promise<RemoteModelSearchResult[]>;
    probeModelVariants(plugin: string, modelId: string): Promise<ModelVariantResponse[]>;
    startDownload(request: DownloadRequest, options?: { handlers?: StreamActionHandlers }): Promise<StreamActionHandle>;
}

interface DownloadRequest {
    plugin?: string;
    modelId?: string;
    universalId?: string;
    quantization?: string;
    displayName?: string;
    modelName?: string;
}

interface DownloadModalSessionPort {
    modals: ModalPresenterApi;
    requireUI(selector: string | Element, context?: Element): Element;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    showNotification(message: string, type?: NotificationType, duration?: number): void;
    api: DownloadModalApi;
    dom: {
        hasClass(target: Element, className: string): boolean;
    };
    sanitizer: Sanitizer;
    getIconSync(name: IconName, options?: IconOptions): TrustedHtml;
    isAdmin(): boolean;
    consumeInitialActionContext(): { action?: string; plugin?: string; vm?: string } | null;
    getClipboardService(): ClipboardApi;
    copyToClipboard(text: string, options?: CopyToClipboardOptions): Promise<void>;
    setLocationHash(hash: string): void;
}

interface DownloadModalExecutionPort {
    streams: StreamTracker;
    variantProbe: VariantProbeController;
    getAvailablePlugins(): PluginRecord[];
    refreshModelsAfterCatalogMutation(): void;
    requireStreamManager(): StreamManagerContract;
    createStreamHandlers(streamId: string, message: string, options: { onProgress?: (event: JsonValue | null | undefined) => void }): StreamActionHandlers;
    modelActions: ModelActions;
}

interface DownloadModalCatalogPort {
    loadPlugins(options?: { force?: boolean }): Promise<PluginRecord[]>;
    refreshPluginCaches(plugins?: ReadonlyArray<PluginRecord> | null): void;
    getDownloadPlugins(): PluginRecord[];
    getProviderPlugins(): PluginRecord[];
    isDownloadPluginOperational(plugin: PluginRecord): boolean;
    isProviderPluginOperational(plugin: PluginRecord): boolean;
    getPluginByName(name: string): PluginRecord | null;
    updateProviderButtonVisibility(): void;
}

interface DownloadModalViewPort {
    setUIValue(
        target: string | Element,
        value: JsonValue | null | undefined,
        options?: {
            formatter?: (value: JsonValue | null | undefined, element: Element) => JsonValue | null | undefined;
            attribute?: string;
            allowNull?: boolean;
        },
        context?: Element
    ): void;
    optionalUI(selector: string | Element, context?: Element): Element | null;
    optionalHTMLElement(selector: string | Element, context?: Element): HTMLElement | null;
    queryUI(selector: string | string[] | Element, context?: Element): Element[];
    addClassName(target: string | Element, className: string, context?: Element): void;
    removeClassName(target: string | Element, className: string, context?: Element): void;
    toggleClassName(target: string | Element, className: string, force?: boolean, context?: Element): void;
    updateHTML(target: string | Element | null, content: TrustedHtml | string, options?: { escape?: boolean }, context?: Element): void;
    updateText(target: string | Element | null, text: string, context?: Element): void;
    updateProperty(target: string | Element, property: string, value: DomPropertyValue, context?: Element): void;
    updateAttribute(target: string | Element, attribute: string, value: string | null, context?: Element): void;
    updateStyle(target: string | Element, property: string, value: string, context?: Element): void;
    setButtonLoading(target: string | Element, loading: boolean, options?: SetButtonLoadingOptions): void;
}

interface DownloadModalHost {
    session: DownloadModalSessionPort;
    execution: DownloadModalExecutionPort;
    catalog: DownloadModalCatalogPort;
    view: DownloadModalViewPort;
}

export type { DownloadModalHost, StreamManagerContract, StreamTracker, VariantProbeController, ModelActions };
