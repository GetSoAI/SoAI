/* SoAI - Logs page log sources service [frontend/assets/ts/pages/logs/services/logsources/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCurrentLocale } from '@core/languageservice/service.ts';
import { handleApiResult } from '@core/api/apiResultHandler.ts';
import type { SystemLogSourcesResponse } from '@core/api/contracts/systemContracts.ts';

const normalizeLogSources = (sources: readonly string[]): readonly string[] => {
    const candidates = sources.map((value) => value.trim()).filter((value) => value.length > 0);
    const unique = Array.from(new Set(candidates));
    const withoutCore = unique.filter((value) => value !== 'core').sort((firstValue, secondValue) => firstValue.localeCompare(secondValue, getCurrentLocale()));
    return unique.includes('core') ? ['core', ...withoutCore] : withoutCore;
};

interface LogSourcesApiClient {
    whenReady(options: { allowDiscovery: boolean }): Promise<string>;
    system: {
        logSources(): Promise<SystemLogSourcesResponse>;
    };
}

const loadAvailableLogSources = async (apiClient: LogSourcesApiClient): Promise<readonly string[]> => {
    await apiClient.whenReady({ allowDiscovery: true });
    const payload = await handleApiResult(apiClient.system.logSources(), {
        boundaryName: 'LogsPage',
        rethrow: true,
        notifyOnError: true,
        logErrors: true
    });
    if (payload === null) {
        throw new Error('Log sources response is unavailable');
    }
    const normalized = normalizeLogSources(payload.sources);
    if (normalized.length === 0) {
        throw new Error('Log sources response must include at least one source');
    }
    return normalized;
};

export { loadAvailableLogSources };
