/* SoAI - Providers refresh aggregate and ownership contracts [frontend/assets/ts/features/models/modals/providersmodal/providersRefreshContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ExternalProviderRecord } from '@core/api/contracts/pluginProviderContracts.ts';

type ProvidersRefreshStatus = 'ready' | 'degraded' | 'unavailable';

interface ProviderRefreshFailure {
    pluginName: string;
    error: Error;
}

interface ProvidersRefreshResult {
    providers: readonly ExternalProviderRecord[];
    requestedPlugins: readonly string[];
    successfulPlugins: readonly string[];
    failures: readonly ProviderRefreshFailure[];
    sourcePluginRevision: number;
    status: ProvidersRefreshStatus;
}

interface ProvidersRefreshControllerDependencies {
    fetchPlugin(pluginName: string, signal: AbortSignal): Promise<ExternalProviderRecord[]>;
    publish(result: ProvidersRefreshResult): void;
    reportFailure(failures: readonly ProviderRefreshFailure[]): void;
    concurrency: number;
}

export type { ProviderRefreshFailure, ProvidersRefreshControllerDependencies, ProvidersRefreshResult, ProvidersRefreshStatus };
