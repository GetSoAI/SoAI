/* SoAI - Shared language service implementation [frontend/assets/ts/core/languageservice/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { dispatchCustomEvent, getGlobalScope } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isArray, isFunction, isString, hasOwn } from '@core/typeGuards.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { initializeLanguageService } from '@core/languageservice/events.ts';
import { loadLanguageFile, loadLanguageFlags, loadManifest } from '@core/languageservice/effects.ts';
import { EVENT_CHANGE, PRIMARY_LANGUAGE, SERVICE_NAME } from '@core/languageservice/constants.ts';
import { resolveStorage } from '@core/languageservice/adapters.ts';
import { isTranslationObject } from '@core/languageservice/guards.ts';
import { formatLocalizedDate, formatLocalizedNumber, getResolvedLocalizationLocale } from '@core/localization/public.ts';
import type { JsonRecord } from '@core/types/jsonValues.ts';
import type { LanguageEntry, LanguageEntryWithFlag, LanguageManifest, TranslationObject, TranslationValue } from '@core/languageservice/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveSupportedLanguageCode } from '@core/languageservice/mappers.ts';

if (!isFunction(ResourceTracker)) {
    throw new Error('LanguageService requires ResourceTracker');
}

class LanguageService {
    languages: Map<string, LanguageEntry> = new Map();
    currentLanguage: string = PRIMARY_LANGUAGE;
    defaultLanguage: string = PRIMARY_LANGUAGE;
    loadedLanguages: Map<string, TranslationObject> = new Map();
    loadingLanguages: Map<string, Promise<TranslationObject>> = new Map();
    languageFlags: Map<string, string> = new Map();
    manifest: LanguageManifest | null = null;
    initialized: boolean = false;
    initializePromise: Promise<void> | null = null;
    catalogPaths: readonly string[] = Object.freeze([]);
    resources: ResourceTracker = new ResourceTracker();
    #requestedLanguage: string = PRIMARY_LANGUAGE;
    readonly #languageRequests = new LatestRequestController();
    #languageNotificationTimer: number | null = null;

    configureCatalogs(catalogPaths: readonly string[]): void {
        if (this.initialized || this.initializePromise !== null || this.loadedLanguages.size > 0) {
            throw new Error('Translation catalogs must be configured before language initialization');
        }
        if (catalogPaths.some((catalogPath) => !catalogPath.trim())) {
            throw new Error('Translation catalog paths must be non-empty');
        }
        this.catalogPaths = Object.freeze([...catalogPaths]);
    }

    async initialize(): Promise<void> {
        if (this.initialized) {
            return;
        }
        if (!this.initializePromise) {
            this.initializePromise = initializeLanguageService(this)
                .then(() => {
                    this.initialized = true;
                })
                .finally(() => {
                    this.initializePromise = null;
                });
        }
        const promise = this.initializePromise;
        if (!promise) {
            return;
        }
        return promise;
    }

    async loadManifest(): Promise<void> {
        await loadManifest(this);
    }

    async loadLanguageFlags(): Promise<void> {
        await loadLanguageFlags(this);
    }

    async loadLanguageFile(code: string): Promise<TranslationObject> {
        return loadLanguageFile(this, code);
    }

    detectBrowserLanguage(): string {
        const navigatorRef = getGlobalScope()?.navigator;
        if (!navigatorRef) {
            throw new Error('Navigator unavailable for language detection');
        }
        const candidates = isArray(navigatorRef.languages) ? navigatorRef.languages.filter((value): value is string => isString(value) && Boolean(value.trim())) : [];
        if (isString(navigatorRef.language) && navigatorRef.language.trim() && !candidates.includes(navigatorRef.language)) {
            candidates.push(navigatorRef.language);
        }
        if (candidates.length === 0) {
            throw new Error('Browser language could not be determined');
        }
        const code = resolveSupportedLanguageCode(candidates, Array.from(this.languages.keys()));
        if (!code) {
            throw new Error(`Unsupported browser languages: ${candidates.join(', ')}`);
        }
        return code;
    }

    async setLanguage(code: string): Promise<void> {
        if (!this.languages.has(code)) {
            throw new Error(`Unsupported language: ${code}`);
        }
        this.#requestedLanguage = code;
        await this.#languageRequests.runLatest(async (request) => {
            if (code === this.currentLanguage && this.loadedLanguages.has(code)) {
                return;
            }
            await this.loadLanguageFile(code);
            if (request.isStale()) {
                return;
            }
            this.currentLanguage = code;
            this.applyDocumentLanguage();

            const storage = resolveStorage();
            if (storage?.setLanguage) {
                storage.setLanguage(code);
            }
            if (this.initialized) {
                this.#scheduleLanguageChangeNotification(code);
            }
        });
    }

    getLanguage(): string {
        return this.currentLanguage;
    }

    isLanguageRequestSettled(code: string): boolean {
        return code === this.currentLanguage && code === this.#requestedLanguage;
    }

    getAvailableLanguages(): LanguageEntryWithFlag[] {
        return Array.from(this.languages.values()).map((entry) => {
            const flag = this.languageFlags.get(entry.code);
            return flag === undefined ? { ...entry } : { ...entry, flag };
        });
    }

    getLanguageFlag(code: string): string | undefined {
        return this.languageFlags.get(code);
    }

    notifyLanguageChange(code: string): void {
        dispatchCustomEvent(EVENT_CHANGE, { language: code });
    }

    #scheduleLanguageChangeNotification(code: string): void {
        if (this.#languageNotificationTimer !== null) {
            this.resources.clearTimeout(this.#languageNotificationTimer);
        }
        this.#languageNotificationTimer = this.resources.setTimeout(() => {
            this.#languageNotificationTimer = null;
            if (this.isLanguageRequestSettled(code)) {
                this.notifyLanguageChange(code);
            }
        }, 0);
    }

    t(key: string, parameters: JsonRecord = {}): string {
        if (!key) {
            throw new Error('Translation key is required');
        }
        const value = this.getTranslation(key, this.currentLanguage);
        if (value === null) {
            throw new Error(`Missing translation for key ${key} in ${this.currentLanguage}`);
        }
        return this.interpolate(value, parameters);
    }

    getTranslation(key: string, langCode: string): string | null;
    getTranslation(key: string, langCode?: string | null): string | null;
    getTranslation(key: string, langCode: string | null = null): string | null {
        const resolvedLanguage = isString(langCode) && langCode ? langCode : this.currentLanguage;
        const initialLanguage = this.loadedLanguages.get(resolvedLanguage);
        if (!initialLanguage) {
            return null;
        }
        let current: TranslationValue = initialLanguage;
        const pathSegments = key.split('.');
        for (const segment of pathSegments) {
            if (!isTranslationObject(current) || !hasOwn(current, segment)) {
                return null;
            }
            const translationObject: TranslationObject = current;
            const nextValue: TranslationValue | undefined = translationObject[segment];
            if (nextValue === undefined) {
                return null;
            }
            current = nextValue;
        }
        return isString(current) ? current : null;
    }

    interpolate(template: string, parameters: JsonRecord): string {
        if (!parameters || !Object.keys(parameters).length) {
            return template;
        }
        return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in parameters ? String(parameters[key]) : match));
    }

    plural(key: string, count: number, parameters: JsonRecord = {}): string {
        const pluralKey = `${key}.${count === 1 ? 'singular' : 'plural'}`;
        const value = this.getTranslation(pluralKey, this.currentLanguage);
        if (value === null) {
            throw new Error(`Missing translation for key ${pluralKey} in ${this.currentLanguage}`);
        }
        return this.interpolate(value, { ...parameters, count });
    }

    formatNumber(value: number, options: Intl.NumberFormatOptions = {}): string {
        try {
            return formatLocalizedNumber(value, options);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error(SERVICE_NAME, 'Formatting number failed', runtimeError);
            return String(value);
        }
    }

    formatDate(date: Date, options: Intl.DateTimeFormatOptions = {}): string {
        try {
            return formatLocalizedDate(date, options);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error(SERVICE_NAME, 'Formatting date failed', runtimeError);
            return date.toString();
        }
    }

    getLocale(): string {
        return getResolvedLocalizationLocale();
    }

    getDirection(): 'ltr' | 'rtl' {
        return this.languages.get(this.currentLanguage)?.direction || 'ltr';
    }

    applyDocumentLanguage(): void {
        try {
            const document = dom.getDocument();
            if (document?.documentElement) {
                document.documentElement.setAttribute('lang', this.currentLanguage);
                document.documentElement.setAttribute('dir', 'ltr');
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug(SERVICE_NAME, 'Failed to apply document language', runtimeError);
        }
    }

    reset(): void {
        this.#languageRequests.invalidate();
        this.resources.cleanup();
        this.#languageNotificationTimer = null;
        this.resources = new ResourceTracker();
        this.languages.clear();
        this.loadedLanguages.clear();
        this.loadingLanguages.clear();
        this.languageFlags.clear();
        this.manifest = null;
        this.currentLanguage = PRIMARY_LANGUAGE;
        this.#requestedLanguage = PRIMARY_LANGUAGE;
        this.defaultLanguage = PRIMARY_LANGUAGE;
        this.initialized = false;
        this.initializePromise = null;
        this.catalogPaths = Object.freeze([]);
    }
}

let languageServiceInstance: LanguageService | null = null;

const getLanguageService = (): LanguageService => {
    if (!languageServiceInstance) {
        languageServiceInstance = new LanguageService();
    }
    return languageServiceInstance;
};

const resetLanguageService = (): void => {
    if (!languageServiceInstance) {
        return;
    }
    languageServiceInstance.reset();
    languageServiceInstance = null;
};

const getCurrentLocale = (): string => getResolvedLocalizationLocale();

export { LanguageService, getCurrentLocale, getLanguageService, resetLanguageService };
export type { LanguageEntry, LanguageEntryWithFlag, TranslationObject, TranslationValue };
