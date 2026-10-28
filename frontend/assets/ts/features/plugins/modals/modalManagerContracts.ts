/* SoAI - Plugin modal manager contracts [frontend/assets/ts/features/plugins/modals/modalManagerContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { EscapeSanitizerApi } from '@core/security/protocols.ts';
import type { StatusManager } from '@core/state/statusmanager/service.ts';
import type { HardwareApi } from '@features/plugins/modals/config/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { BackendUpdateAccess } from '@core/plugins/backendUpdates.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { BackendOperationHost } from '@features/plugins/modals/backend/backendTypes.ts';
import type { ManageBackendModalManager } from '@features/plugins/modals/backend/managebackendmodal/service.ts';
import type { CloneModalManager } from '@features/plugins/modals/CloneModalManager.ts';
import type { ConcurrentModalManager } from '@features/plugins/modals/ConcurrentModalManager.ts';
import type { ConfigManager } from '@features/plugins/modals/ConfigManager.ts';
import type { DownloadManagerHost, PluginDownloadModalManager } from '@features/plugins/modals/downloadmanager/service.ts';
import type { InfoManager } from '@features/plugins/modals/InfoManager.ts';
import type { PluginCapabilityDescriptor } from '@features/plugins/modals/info/types.ts';
import type { PluginsManagerHostCallbacks } from '@features/plugins/modals/modalCallbacks.ts';
import type { ConfigUpdateResponse } from '@core/api/contracts/configContracts.ts';
import type { BackendVariantsResponse, PluginBackendUpdateStatus } from '@core/api/contracts/pluginManagementContracts.ts';
import type { ManageBackendManagerHost } from '@features/plugins/modals/backend/managebackendmodal/types.ts';

interface PluginsModalManagers {
    downloadModalManager: PluginDownloadModalManager;
    configManager: ConfigManager;
    infoManager: InfoManager;
    concurrentManager: ConcurrentModalManager;
    manageBackendModalManager: ManageBackendModalManager;
    cloneManager: CloneModalManager;
}

interface PluginsModalDomApi {
    getData(element: Element, key: string): string | null;
    setData(element: Element, key: string, value: string): void;
}

interface PluginsModalManagersApi {
    uploadFile: DownloadManagerHost['execution']['api']['uploadFile'];
    plugins: DownloadManagerHost['execution']['api']['plugins'];
    configs: {
        get(name: string): Promise<JsonObject>;
        update(name: string, config: JsonValue): Promise<ConfigUpdateResponse>;
    };
    hardware: HardwareApi;
}

interface PluginsModalFoundationPort {
    callbacks: PluginsManagerHostCallbacks;
    security: EscapeSanitizerApi;
    statusManager: StatusManager | null;
    dom: PluginsModalDomApi;
    streams: DownloadManagerHost['execution']['streams'];
    api: PluginsModalManagersApi;
}

interface PluginsModalConcurrencyPort {
    getMaxConcurrentPlugins(): number | null;
    setMaxConcurrentPlugins(value: number | null): void;
    getConcurrentPluginsOriginalValue(): number | null;
    setConcurrentPluginsOriginalValue(value: number | null): void;
    getCoreConfigCache(): JsonObject | null;
    setCoreConfigCache(value: JsonObject | null): void;
}

interface PluginsModalOperationPort {
    updateStats(): void;
    loadCoreConfig(options?: { force?: boolean }): Promise<void>;
    createStreamHandlers: BackendOperationHost['createStreamHandlers'];
    trackAcceptedTask: DownloadManagerHost['execution']['trackAcceptedTask'];
    startTaskAction: BackendOperationHost['startTaskAction'];
    startTaskCommand: BackendOperationHost['startTaskCommand'];
    beginOptimisticOperation: BackendOperationHost['beginOptimisticOperation'];
    cancelDownload: DownloadManagerHost['execution']['cancelDownload'];
    createOperationProgressReporter: DownloadManagerHost['execution']['createOperationProgressReporter'];
    hasClipboardSupport: DownloadManagerHost['session']['hasClipboardSupport'];
    isAdmin: DownloadManagerHost['session']['isAdmin'];
    setLocationHash(hash: string): void;
}

interface PluginsModalPresentationPort {
    getCapabilityDescriptors(plugin: PluginRecord): readonly PluginCapabilityDescriptor[];
    checkBackendInstallationSupport(plugin: PluginRecord): boolean;
    isPluginPermanentlyDisabled(plugin: PluginRecord): boolean;
    notifyPluginIncompatible(plugin: PluginRecord): void;
    handleBackendWebsiteLinkClick(event: Event): Promise<void>;
    getBackendStatus(plugin: PluginRecord): string;
    getBackendVersion(plugin: PluginRecord): string;
    getPluginStatus(plugin: PluginRecord): string;
    formatPluginName(name: string): string;
}

interface PluginsModalStatePort {
    backendUpdateAccess(plugin: PluginRecord): BackendUpdateAccess;
    subscribeBackendUpdateAccess(listener: () => void): () => void;
    catalog: ManageBackendManagerHost['catalog'];
    subscribeModalLedUpdates(): void;
    unsubscribeModalLedUpdates(): void;
    setCurrentManagingPlugin(plugin: PluginRecord | null): void;
    setCurrentUpdateInfo(info: PluginBackendUpdateStatus | null): void;
}

interface PluginsModalUpdatePort {
    normalizeVersion(value: JsonValue | null | undefined): { raw: string | null; safe: string | null };
    checkBackendUpdate(pluginName: string, options?: { signal?: AbortSignal }): Promise<PluginBackendUpdateStatus>;
    getBackendVariants(pluginName: string, options?: { signal?: AbortSignal }): Promise<BackendVariantsResponse>;
    saveBackendVariantSelection(pluginName: string, variantId: string): Promise<BackendVariantsResponse>;
}

interface PluginsModalProgressPort {
    setPluginProgressMeta(key: string, meta: Record<string, JsonValue | null | undefined>): void;
    consumePluginProgressMeta(key: string): Record<string, JsonValue | null | undefined> | null;
    isPluginIncompatible(plugin: PluginRecord): boolean;
}

interface PluginsModalManagersDependencies {
    foundation: PluginsModalFoundationPort;
    concurrency: PluginsModalConcurrencyPort;
    operations: PluginsModalOperationPort;
    presentation: PluginsModalPresentationPort;
    state: PluginsModalStatePort;
    updates: PluginsModalUpdatePort;
    progress: PluginsModalProgressPort;
}

export type { PluginsModalManagers, PluginsModalManagersDependencies };
