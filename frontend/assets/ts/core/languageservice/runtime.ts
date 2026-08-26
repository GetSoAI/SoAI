/* SoAI - Shared language service runtime [frontend/assets/ts/core/languageservice/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperties, isObject } from '@core/typeGuards.ts';
import type { JsonRecord, JsonValue } from '@core/types/jsonValues.ts';

interface LanguageRuntime {
    t: (key: string, parameters?: JsonRecord) => string;
    plural: (key: string, count: number, parameters?: JsonRecord) => string;
    formatNumber: (value: number, options?: Intl.NumberFormatOptions) => string;
    formatDate: (date: Date, options?: Intl.DateTimeFormatOptions) => string;
}

declare global {
    var __soai_language_runtime__: LanguageRuntime | undefined;
}

let languageRuntimeRef: LanguageRuntime | null = null;

const isLanguageRuntime = (value: LanguageRuntime | JsonValue | null | undefined): value is LanguageRuntime => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperties(value, ['t', 'plural', 'formatNumber', 'formatDate']);
};

const setLanguageRuntime = (runtime: LanguageRuntime): void => {
    if (!isLanguageRuntime(runtime)) {
        throw new Error('Language runtime must expose t(), plural(), formatNumber(), and formatDate()');
    }
    languageRuntimeRef = runtime;
    globalThis.__soai_language_runtime__ = runtime;
};

const getLanguageRuntime = (): LanguageRuntime => {
    if (languageRuntimeRef) {
        return languageRuntimeRef;
    }
    const candidate = globalThis.__soai_language_runtime__;
    if (!isLanguageRuntime(candidate)) {
        throw new Error('Language runtime is not initialized. Install it during bootstrap.');
    }
    languageRuntimeRef = candidate;
    return candidate;
};

const resetLanguageRuntime = (): void => {
    languageRuntimeRef = null;
    globalThis.__soai_language_runtime__ = undefined;
};

export { getLanguageRuntime, resetLanguageRuntime, setLanguageRuntime };
export type { LanguageRuntime };
