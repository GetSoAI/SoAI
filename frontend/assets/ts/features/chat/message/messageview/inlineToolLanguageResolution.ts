/* SoAI - Inline tool field language resolution [frontend/assets/ts/features/chat/message/messageview/inlineToolLanguageResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeLanguageId } from '@core/syntaxhighlighter/service.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

const CONTENT_FIELD_KEYS: ReadonlySet<string> = new Set<string>(['content']);

const PATH_LANGUAGE_HINTS: Readonly<Record<string, string>> = Object.freeze({
    dockerfile: 'dockerfile',
    gitignore: 'plaintext',
    jsonl: 'json',
    log: 'plaintext',
    mdx: 'markdown',
    toml: 'plaintext',
    txt: 'plaintext',
    yaml: 'yaml'
});

const resolveLanguageFromPath = (path: string): string | null => {
    const normalizedPath = path.trim().toLowerCase();
    if (!normalizedPath) {
        return null;
    }
    const segments = normalizedPath.split('/');
    const leafName = segments.length > 0 ? (segments[segments.length - 1] ?? '') : '';
    const normalizedLeafName = leafName.trim();
    if (!normalizedLeafName) {
        return null;
    }
    const explicitLeafLanguage = normalizeLanguageId(normalizedLeafName);
    if (explicitLeafLanguage) {
        return explicitLeafLanguage;
    }
    const hintedLeafLanguage = PATH_LANGUAGE_HINTS[normalizedLeafName];
    if (hintedLeafLanguage) {
        return hintedLeafLanguage;
    }
    const extensionIndex = normalizedLeafName.lastIndexOf('.');
    if (extensionIndex < 0 || extensionIndex >= normalizedLeafName.length - 1) {
        return null;
    }
    const extension = normalizedLeafName.slice(extensionIndex + 1);
    return normalizeLanguageId(extension) ?? PATH_LANGUAGE_HINTS[extension] ?? null;
};

const resolveStructuredFieldLanguage = (key: string, value: JsonValue | undefined, record: JsonObject): string | null => {
    if (!CONTENT_FIELD_KEYS.has(key) || !isString(value)) {
        return null;
    }
    const pathValue = record['path'];
    if (!isString(pathValue)) {
        return null;
    }
    return resolveLanguageFromPath(pathValue);
};

export { resolveStructuredFieldLanguage };
