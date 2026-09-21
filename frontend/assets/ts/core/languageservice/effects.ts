/* SoAI - Shared language service effects [frontend/assets/ts/core/languageservice/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { hasOwn, isArray, isObject, isString } from '@core/typeGuards.ts';
import { buildLanguageUrl, buildTranslationCatalogUrl, resolveApiClient, resolveAssetUrl } from '@core/languageservice/adapters.ts';
import { mergeTranslationObjects, normalizeTranslationRoot, parseLanguageManifest, resolveManifestDefaultLanguage } from '@core/languageservice/mappers.ts';
import { FLAGS_FILE, LANGUAGES_PATH, MANIFEST_FILE, SERVICE_NAME } from '@core/languageservice/constants.ts';
import type { LanguageServiceRuntime } from '@core/languageservice/internalContracts.ts';
import type { TranslationObject } from '@core/languageservice/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

const loadManifest = async (service: LanguageServiceRuntime): Promise<void> => {
    const apiClient = await resolveApiClient();
    const path = resolveAssetUrl(`${LANGUAGES_PATH}/${MANIFEST_FILE}`);
    const manifestValue = await apiClient.fetchAsset(path, { responseType: 'json' });
    const manifest = parseLanguageManifest(manifestValue);
    service.manifest = manifest;

    const defaultLanguage = resolveManifestDefaultLanguage(service.manifest);
    if (!defaultLanguage) {
        throw new Error('Manifest must define default language');
    }
    service.defaultLanguage = service.currentLanguage = defaultLanguage;

    const languages = service.manifest.languages;
    if (!isArray(languages) || !languages.length) {
        throw new Error('Invalid manifest structure');
    }

    service.languages.clear();
    languages.forEach((languageEntry) => {
        if (!languageEntry?.code) {
            throw new Error('Language entry is missing code');
        }
        service.languages.set(languageEntry.code, {
            code: languageEntry.code,
            name: languageEntry.name,
            direction: languageEntry.direction || 'ltr',
            region: languageEntry.region || null
        });
    });

    if (!service.languages.has(service.defaultLanguage)) {
        throw new Error('Manifest default language is not present in language list');
    }
};

const loadLanguageFlags = async (service: LanguageServiceRuntime): Promise<void> => {
    try {
        const apiClient = await resolveApiClient();
        const path = resolveAssetUrl(`${LANGUAGES_PATH}/${FLAGS_FILE}`);
        const flags = await apiClient.fetchAsset(path, { responseType: 'json' });
        if (!isObject(flags)) {
            throw new Error('Language flags payload must be an object');
        }
        for (const [code, flagValue] of Object.entries(flags)) {
            if (isString(flagValue) && flagValue.trim()) {
                service.languageFlags.set(code, flagValue);
            }
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn(SERVICE_NAME, 'Failed to load language flags, continuing without flags', runtimeError);
    }
};

const loadLanguageFile = async (service: LanguageServiceRuntime, code: string): Promise<TranslationObject> => {
    const loaded = service.loadedLanguages.get(code);
    if (loaded) {
        return loaded;
    }
    const pending = service.loadingLanguages.get(code);
    if (pending) {
        return pending;
    }

    const promise = (async (): Promise<TranslationObject> => {
        try {
            const apiClient = await resolveApiClient();
            const path = buildLanguageUrl(service, code);
            const data = await apiClient.fetchAsset(path, { responseType: 'json' });
            if (!isObject(data) || !hasOwn(data, 'translations')) {
                throw new Error(`Invalid language file structure: ${code}.json`);
            }
            let normalized = normalizeTranslationRoot(data['translations']);
            for (const catalogPath of service.catalogPaths) {
                const catalogData = await apiClient.fetchAsset(buildTranslationCatalogUrl(service, catalogPath, code), { responseType: 'json' });
                if (!isObject(catalogData) || !hasOwn(catalogData, 'translations')) {
                    throw new Error(`Invalid translation catalog: ${catalogPath}/${code}.json`);
                }
                normalized = mergeTranslationObjects(normalized, normalizeTranslationRoot(catalogData['translations']));
            }
            service.loadedLanguages.set(code, normalized);
            return normalized;
        } catch (error) {
            const runtimeError = ensureError(error);
            const message = runtimeError.message || 'unknown error';
            throw new Error(`Failed to load language ${code}: ${message}`);
        } finally {
            service.loadingLanguages.delete(code);
        }
    })();
    service.loadingLanguages.set(code, promise);
    return promise;
};

export { loadLanguageFile, loadLanguageFlags, loadManifest };
