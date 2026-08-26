/* SoAI - Shared language service state [frontend/assets/ts/core/languageservice/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { isObject, isString, hasOwn } from '@core/typeGuards.ts';
import { getCacheVersion } from '@core/languageservice/adapters.ts';
import { log } from '@core/languageservice/constants.ts';
import { normalizeTranslationRoot } from '@core/languageservice/mappers.ts';
import type { LanguageServiceRuntime } from '@core/languageservice/internalContracts.ts';
import type { StorageInterface, TranslationObject } from '@core/languageservice/types.ts';

const readCachedTranslations = (service: LanguageServiceRuntime, store: StorageInterface | null, code: string): TranslationObject | null => {
    if (!store?.get) {
        return null;
    }
    const cached = store.get(service.cacheKey, null);
    if (!isObject(cached)) {
        return null;
    }
    const versionValue = cached['version'];
    if (!isString(versionValue) || versionValue !== getCacheVersion(service)) {
        return null;
    }
    const languagesValue = cached['languages'];
    if (!isObject(languagesValue)) {
        return null;
    }
    const entry = languagesValue[code];
    if (!isObject(entry) || !hasOwn(entry, 'translations')) {
        return null;
    }
    const translations = entry['translations'];
    if (!isObject(translations)) {
        return null;
    }
    return normalizeTranslationRoot(translations);
};

const writeCachedTranslations = (service: LanguageServiceRuntime, store: StorageInterface | null, code: string, translations: TranslationObject): void => {
    if (!store?.set) {
        return;
    }
    const version = getCacheVersion(service);
    const existing = store.get(service.cacheKey, null);
    const languages: JsonObject = (() => {
        if (!isObject(existing)) {
            return {};
        }
        const existingVersion = existing['version'];
        if (!isString(existingVersion) || existingVersion !== version) {
            return {};
        }
        const existingLanguages = existing['languages'];
        if (!isJsonObject(existingLanguages)) {
            return {};
        }
        const nextLanguages: JsonObject = {};
        for (const key of Object.keys(existingLanguages)) {
            nextLanguages[key] = existingLanguages[key] ?? null;
        }
        return nextLanguages;
    })();
    languages[code] = { translations: normalizeTranslationRoot(translations) };
    store.set(service.cacheKey, { version, languages });
};

const syncCacheContainer = (service: LanguageServiceRuntime, store: StorageInterface | null): void => {
    if (!store?.set) {
        return;
    }
    const version = getCacheVersion(service);
    const existing = store.get(service.cacheKey, null);
    if (isObject(existing) && existing['version'] === version) {
        return;
    }
    store.set(service.cacheKey, { version, languages: {} });
};

const resolveInitialLanguagePreference = (service: LanguageServiceRuntime, store: StorageInterface | null): string => {
    const stored = store?.getLanguage?.();
    if (stored) {
        if (service.languages.has(stored)) {
            return stored;
        }
        log('warn', `Ignoring unsupported stored language preference: ${stored}`);
    }
    if (service.languages.has(service.defaultLanguage)) {
        return service.defaultLanguage;
    }
    throw new Error('Unable to resolve initial language preference');
};

export { readCachedTranslations, resolveInitialLanguagePreference, syncCacheContainer, writeCachedTranslations };
