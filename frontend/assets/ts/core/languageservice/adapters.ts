/* SoAI - Shared language service adapters [frontend/assets/ts/core/languageservice/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssetPath } from '@core/assetPaths.ts';
import { getApiClient } from '@core/api/service.ts';
import { encodeSegment } from '@core/identifiers.ts';
import { isApiClient } from '@core/languageservice/guards.ts';
import { getStorageService } from '@core/storage/runtime.ts';
import { isKeyValueStorageContract } from '@core/storage/guards.ts';
import { isString } from '@core/typeGuards.ts';
import { LANGUAGES_PATH } from '@core/languageservice/constants.ts';
import type { ApiClient, StorageInterface } from '@core/languageservice/types.ts';
import type { LanguageServiceRuntime } from '@core/languageservice/internalContracts.ts';

const resolveStorage = (): StorageInterface | null => {
    const candidate = getStorageService();
    if (!candidate) return null;
    return isKeyValueStorageContract(candidate) ? candidate : null;
};

const resolveAssetUrl = (path: string): string => {
    const resolved = resolveAssetPath(path);
    if (!resolved) {
        throw new Error(`Language asset path resolution failed: ${path}`);
    }
    return resolved;
};

const resolveApiClient = async (): Promise<ApiClient> => {
    const candidate = getApiClient();
    if (!isApiClient(candidate)) {
        throw new Error('ApiClient must expose fetchAsset(path, options)');
    }
    return candidate;
};

const getCacheVersion = (service: LanguageServiceRuntime): string => {
    const version = service.manifest?.version;
    const manifestVersion = isString(version) && version.trim() ? version.trim() : 'unversioned';
    return service.catalogPaths.length > 0 ? `${manifestVersion}:${service.catalogPaths.join(',')}` : manifestVersion;
};

const buildLanguageUrl = (service: LanguageServiceRuntime, code: string): string => {
    const version = getCacheVersion(service);
    const cacheToken = version ? `?v=${encodeSegment(version)}` : '';
    return resolveAssetUrl(`${LANGUAGES_PATH}/${code}.json${cacheToken}`);
};

const buildTranslationCatalogUrl = (service: LanguageServiceRuntime, catalogPath: string, code: string): string => {
    const version = getCacheVersion(service);
    return resolveAssetUrl(`${catalogPath}/${code}.json?v=${encodeSegment(version)}`);
};

export { buildLanguageUrl, buildTranslationCatalogUrl, getCacheVersion, resolveApiClient, resolveAssetUrl, resolveStorage };
