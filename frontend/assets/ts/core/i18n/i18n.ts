/* SoAI - Single translation entrypoint wrapping the runtime language service with typed keys [frontend/assets/ts/core/i18n/i18n.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { getLanguageRuntime } from '@core/languageservice/runtime.ts';
import { isFiniteNumber, isFunction, isString } from '@core/typeGuards.ts';
import type { JsonRecord } from '@core/types/jsonValues.ts';
import type { PluralBaseKey, TranslationKey } from '@core/i18n/translationKeyContract.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface SanitizerContract {
    html: (value: string) => string;
    attribute: (value: string) => string;
}

const translate = (key: TranslationKey, parameters?: JsonRecord): string => {
    if (!key) {
        throw new Error('Translation key is required');
    }
    const service = getLanguageRuntime();
    try {
        const result = service.t(key, parameters);
        if (!isString(result) || !result) {
            throw new Error(`Translation missing for key ${key}`);
        }
        return result;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('Translation', `Translation failed for key ${key}`, runtimeError);
        throw runtimeError;
    }
};

const plural = (baseKey: PluralBaseKey, count: number, parameters?: JsonRecord): string => {
    if (!baseKey) {
        throw new Error('Plural key is required');
    }
    if (!isFiniteNumber(count)) {
        throw new Error('Plural count must be numeric');
    }
    const service = getLanguageRuntime();
    if (!isFunction(service.plural)) {
        throw new Error('Language service must expose plural()');
    }
    try {
        const result = service.plural(baseKey, count, parameters);
        if (!isString(result) || !result) {
            throw new Error(`Plural translation missing for key ${baseKey}`);
        }
        return result;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('Translation', `Plural translation failed for key ${baseKey}`, runtimeError);
        throw runtimeError;
    }
};

const html = (sanitizer: SanitizerContract, key: TranslationKey, parameters?: JsonRecord): string => {
    if (!sanitizer || !isFunction(sanitizer.html)) {
        throw new Error('Sanitizer must expose html()');
    }
    return sanitizer.html(translate(key, parameters));
};

const attr = (sanitizer: SanitizerContract, key: TranslationKey, parameters?: JsonRecord): string => {
    if (!sanitizer || !isFunction(sanitizer.attribute)) {
        throw new Error('Sanitizer must expose attribute()');
    }
    return sanitizer.attribute(translate(key, parameters));
};

const formatNumber = (value: number, options: Intl.NumberFormatOptions = {}): string => {
    if (!isFiniteNumber(value)) {
        throw new Error('Number value must be numeric');
    }
    const service = getLanguageRuntime();
    if (!isFunction(service.formatNumber)) {
        throw new Error('Language service must expose formatNumber()');
    }
    return service.formatNumber(value, options);
};

const formatDate = (date: Date, options: Intl.DateTimeFormatOptions = {}): string => {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
        throw new Error('Date value must be a valid Date');
    }
    const service = getLanguageRuntime();
    if (!isFunction(service.formatDate)) {
        throw new Error('Language service must expose formatDate()');
    }
    return service.formatDate(date, options);
};

export const i18n = { t: translate, plural, html, attr, formatNumber, formatDate };
export type { SanitizerContract };
