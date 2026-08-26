/* SoAI - Shared language service internal contracts [frontend/assets/ts/core/languageservice/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LanguageEntry, LanguageManifest, TranslationObject } from '@core/languageservice/types.ts';

interface LanguageServiceRuntimeResources {
    addEventListener: (target: EventTarget, event: string, handler: (event: Event) => void, options?: { passive: boolean }) => () => void;
}

interface LanguageServiceRuntime {
    applyDocumentLanguage(): void;
    cacheKey: string;
    catalogPaths: readonly string[];
    currentLanguage: string;
    defaultLanguage: string;
    initialized: boolean;
    initializePromise: Promise<void> | null;
    languageFlags: Map<string, string>;
    languages: Map<string, LanguageEntry>;
    loadedLanguages: Map<string, TranslationObject>;
    loadingLanguages: Map<string, Promise<TranslationObject>>;
    manifest: LanguageManifest | null;
    resources: LanguageServiceRuntimeResources;
    setLanguage: (code: string) => Promise<void>;
}

interface LoadLanguageOptions {
    service: LanguageServiceRuntime;
    code: string;
}

export type { LanguageServiceRuntime, LoadLanguageOptions };
