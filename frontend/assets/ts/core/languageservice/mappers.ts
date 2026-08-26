/* SoAI - Shared language service mappers [frontend/assets/ts/core/languageservice/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { KEY_SPLIT_RE } from '@core/languageservice/constants.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { isTranslationObject } from '@core/languageservice/guards.ts';
import type { LanguageManifest, ManifestLanguageEntry, TranslationObject, TranslationValue } from '@core/languageservice/types.ts';

type TranslationSource = string | number | boolean | null | undefined | readonly TranslationSource[] | { [key: string]: TranslationSource };
type TranslationSourceRecord = { [key: string]: TranslationSource };

const isTranslationSourceRecord = (value: TranslationSource): value is TranslationSourceRecord => isObject(value) && !isArray(value);

const splitTranslationKey = (rawKey: string): string[] => {
    if (isString(rawKey) && KEY_SPLIT_RE.test(rawKey)) {
        return rawKey.split(KEY_SPLIT_RE).filter((part) => part);
    }
    return [rawKey];
};

const normalizeTranslations = (source: TranslationSource): TranslationValue => {
    if (isArray(source)) {
        return source.map((item) => normalizeTranslations(item));
    }
    if (!isTranslationSourceRecord(source)) {
        return isString(source) ? source : String(source ?? '');
    }

    const result: TranslationObject = {};
    for (const [rawKey, rawValue] of Object.entries(source)) {
        const value = normalizeTranslations(rawValue);
        const parts = splitTranslationKey(rawKey);
        let cursor = result;
        const len = parts.length;

        for (let index = 0; index < len; index++) {
            const part = parts[index];
            if (!part) {
                continue;
            }
            if (index === len - 1) {
                const existing = cursor[part];
                cursor[part] = isTranslationObject(value) && existing !== undefined && isTranslationObject(existing) ? { ...existing, ...value } : value;
            } else {
                const next = cursor[part];
                if (!next || !isTranslationObject(next)) {
                    const child: TranslationObject = {};
                    cursor[part] = child;
                    cursor = child;
                } else {
                    cursor = next;
                }
            }
        }
    }

    return result;
};

const normalizeTranslationRoot = (source: TranslationSource): TranslationObject => {
    const normalized = normalizeTranslations(source);
    if (!isTranslationObject(normalized)) {
        throw new Error('Translations root must be an object');
    }
    return normalized;
};

const mergeTranslationObjects = (base: TranslationObject, overlay: TranslationObject): TranslationObject => {
    const merged: TranslationObject = { ...base };
    for (const [key, overlayValue] of Object.entries(overlay)) {
        const baseValue = merged[key];
        merged[key] = baseValue !== undefined && isTranslationObject(baseValue) && isTranslationObject(overlayValue) ? mergeTranslationObjects(baseValue, overlayValue) : overlayValue;
    }
    return merged;
};

const parseLanguageManifest = (manifestValue: TranslationSource): LanguageManifest => {
    if (!isTranslationSourceRecord(manifestValue)) {
        throw new Error('Language manifest must be an object');
    }

    const parsed: LanguageManifest = {};
    const versionValue = manifestValue['version'];
    if (isString(versionValue) && versionValue.trim()) {
        parsed.version = versionValue.trim();
    }

    const defaultLanguageValue = manifestValue['defaultLanguage'];
    if (isString(defaultLanguageValue) && defaultLanguageValue.trim()) {
        parsed.defaultLanguage = defaultLanguageValue.trim();
    }

    const languagesValue = manifestValue['languages'];
    if (!isArray(languagesValue)) {
        throw new Error('Language manifest must define languages[]');
    }

    const parsedLanguages: ManifestLanguageEntry[] = [];
    for (const entry of languagesValue) {
        if (!isTranslationSourceRecord(entry)) {
            throw new Error('Language manifest languages[] entries must be objects');
        }
        const codeValue = entry['code'];
        const nameValue = entry['name'];
        if (!isString(codeValue) || !codeValue.trim()) {
            throw new Error('Language manifest language entry requires a non-empty code');
        }
        if (!isString(nameValue) || !nameValue.trim()) {
            throw new Error(`Language manifest language ${codeValue} requires a non-empty name`);
        }
        const directionValue = entry['direction'];
        const direction = directionValue === 'rtl' || directionValue === 'ltr' ? directionValue : undefined;
        const regionValue = entry['region'];
        const region = isString(regionValue) && regionValue.trim() ? regionValue.trim() : undefined;

        parsedLanguages.push({
            code: codeValue.trim(),
            name: nameValue.trim(),
            ...(direction ? { direction } : {}),
            ...(region ? { region } : {})
        });
    }

    parsed.languages = parsedLanguages;
    return parsed;
};

const resolveManifestDefaultLanguage = (manifest: LanguageManifest | null): string | null => {
    const defaultLanguage = manifest?.defaultLanguage;
    return isString(defaultLanguage) && defaultLanguage.trim() ? defaultLanguage.trim() : null;
};

const resolveSupportedLanguageCode = (preferredLanguages: readonly string[], supportedCodes: readonly string[]): string | null => {
    const normalizedSupportedCodes = supportedCodes.map((code) => ({ code, normalized: code.toLowerCase() }));

    for (const preferredLanguage of preferredLanguages) {
        const normalizedPreference = preferredLanguage.trim().replaceAll('_', '-').toLowerCase();
        if (!normalizedPreference) {
            continue;
        }

        const exactMatch = normalizedSupportedCodes.find((entry) => entry.normalized === normalizedPreference);
        if (exactMatch) {
            return exactMatch.code;
        }

        const preferenceSegments = normalizedPreference.split('-');
        if (preferenceSegments[0] === 'zh') {
            const traditionalChinese = preferenceSegments.includes('hant') || preferenceSegments.includes('tw') || preferenceSegments.includes('hk') || preferenceSegments.includes('mo');
            if (traditionalChinese) {
                const traditionalMatch = normalizedSupportedCodes.find((entry) => entry.normalized === 'zh-hant');
                if (traditionalMatch) {
                    return traditionalMatch.code;
                }
            }
        }

        const prefixMatches = normalizedSupportedCodes.filter((entry) => normalizedPreference.startsWith(`${entry.normalized}-`)).sort((left, right) => right.normalized.length - left.normalized.length);
        const prefixMatch = prefixMatches[0];
        if (prefixMatch) {
            return prefixMatch.code;
        }
    }

    return null;
};

export { mergeTranslationObjects, normalizeTranslationRoot, normalizeTranslations, parseLanguageManifest, resolveManifestDefaultLanguage, resolveSupportedLanguageCode, splitTranslationKey };
