/* SoAI - Shared language service contracts [frontend/assets/ts/core/languageservice/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface TranslationObject extends JsonObject {
    [key: string]: TranslationValue;
}

type TranslationArray = TranslationValue[];
type TranslationValue = string | TranslationObject | TranslationArray;

interface LanguageEntry {
    code: string;
    name: string;
    direction: 'ltr' | 'rtl';
    region: string | null;
}

interface LanguageEntryWithFlag extends LanguageEntry {
    flag?: string;
}

interface LanguageManifest {
    version?: string;
    defaultLanguage?: string;
    languages?: ManifestLanguageEntry[];
}

interface ManifestLanguageEntry {
    code: string;
    name: string;
    direction?: 'ltr' | 'rtl';
    region?: string;
}

interface StorageInterface {
    ready?: Promise<void>;
    get(key: string, defaultValue: JsonValue | null | undefined): JsonValue | null | undefined;
    set(key: string, value: JsonValue | null | undefined): void;
    getLanguage?(): string | null;
    setLanguage?(code: string): void;
}

interface ApiClient {
    fetchAsset(path: string, options: { responseType: string }): Promise<JsonValue>;
}

export type { ApiClient, LanguageEntry, LanguageEntryWithFlag, LanguageManifest, ManifestLanguageEntry, StorageInterface, TranslationArray, TranslationObject, TranslationValue };
