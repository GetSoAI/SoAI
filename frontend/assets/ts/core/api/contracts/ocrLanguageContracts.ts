/* SoAI - Tesseract language API validation [frontend/assets/ts/core/api/contracts/ocrLanguageContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord, readRequiredJsonObjectArrayValue } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface OcrLanguage {
    code: string;
    name: string;
    nativeName: string;
    flag: string;
    uiLocale: string | null;
    available: boolean;
}

const decodeOcrLanguages = (value: ApiResponsePayload): readonly OcrLanguage[] => {
    const record = requireRecord(value, 'OCR languages');
    const entries = record['languages'];
    if (!Array.isArray(entries)) throw new TypeError('OCR languages must be an array.');
    const languages = readRequiredJsonObjectArrayValue(entries, 'OCR languages').map((entry): OcrLanguage => {
        const uiLocale = entry['ui_locale'];
        return {
            code: readRequiredStringValue(entry['code'], 'OCR model code'),
            name: readRequiredStringValue(entry['name'], 'OCR model name'),
            nativeName: readRequiredStringValue(entry['native_name'], 'OCR native name'),
            flag: readRequiredStringValue(entry['flag'], 'OCR flag'),
            uiLocale: uiLocale === null ? null : readRequiredStringValue(uiLocale, 'OCR UI locale'),
            available: readRequiredBooleanValue(entry['available'], 'OCR availability')
        };
    });
    if (!languages.length || new Set(languages.map((entry) => entry.code)).size !== languages.length || languages.some((entry) => !/^[a-z]{3}(?:_[a-z]+)*$/.test(entry.code) || !entry.name || !entry.nativeName)) {
        throw new TypeError('OCR catalog has invalid model identities.');
    }
    return languages;
};

const requireOcrLanguage = (value: JsonValue | undefined, languages: readonly OcrLanguage[]): string => {
    const code = readRequiredStringValue(value, 'OCR language');
    if (!languages.some((entry) => entry.code === code)) throw new TypeError('Unsupported OCR language.');
    return code;
};

const readOcrPreference = (preferences: JsonObject, languages: readonly OcrLanguage[]): string => {
    const settings = preferences['settings'];
    if (settings === undefined) return requireOcrLanguage('eng', languages);
    const record = requireRecord(settings, 'OCR preferences');
    return requireOcrLanguage(record['ocr_language'] === undefined ? 'eng' : record['ocr_language'], languages);
};

export { decodeOcrLanguages, readOcrPreference, requireOcrLanguage };
export type { OcrLanguage };
