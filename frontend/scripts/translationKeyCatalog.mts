/* SoAI - Frontend translation key catalog normalization [frontend/scripts/translationKeyCatalog.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const KEY_SPLIT_RE = /[.:]/;

type JsonPrimitive = string | number | boolean | null;
type JsonValue = JsonPrimitive | JsonObject | JsonValue[];
interface JsonObject {
    [key: string]: JsonValue;
}

const isObject = (value: JsonValue): value is JsonObject => typeof value === 'object' && value !== null && !Array.isArray(value);
const isString = (value: JsonValue): value is string => typeof value === 'string';

const splitTranslationKey = (rawKey: string): string[] => {
    if (KEY_SPLIT_RE.test(rawKey)) {
        return rawKey.split(KEY_SPLIT_RE).filter((part) => part);
    }
    return [rawKey];
};

const normalizeTranslations = (source: JsonValue): JsonValue => {
    if (Array.isArray(source)) {
        return source.map((item) => normalizeTranslations(item));
    }
    if (!isObject(source)) {
        if (isString(source)) {
            return source;
        }
        throw new Error('frontend/assets/lang/en.json translations must contain only nested objects and leaf strings');
    }

    const result: JsonObject = {};
    for (const [rawKey, rawValue] of Object.entries(source)) {
        const value = normalizeTranslations(rawValue);
        const parts = splitTranslationKey(rawKey);
        let cursor: JsonObject = result;
        const len = parts.length;

        for (let index = 0; index < len; index += 1) {
            const part = parts[index];
            if (!part) {
                continue;
            }
            if (index === len - 1) {
                const existing = cursor[part];
                if (isObject(value) && existing !== undefined && isObject(existing)) {
                    cursor[part] = { ...existing, ...value };
                } else {
                    cursor[part] = value;
                }
            } else {
                const next = cursor[part];
                if (!next || !isObject(next)) {
                    const child: JsonObject = {};
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

const flattenLeafStringKeys = (source: JsonValue, prefix: string, acc: Set<string>): void => {
    if (!isObject(source)) {
        return;
    }
    for (const [key, value] of Object.entries(source)) {
        const nextPrefix = prefix ? `${prefix}.${key}` : key;
        if (isString(value)) {
            acc.add(nextPrefix);
            continue;
        }
        flattenLeafStringKeys(value, nextPrefix, acc);
    }
};

const detectPluralBaseKeys = (keys: Set<string>): string[] => {
    const states = new Map<string, { singular: boolean; plural: boolean }>();
    for (const key of keys) {
        if (key.endsWith('.singular')) {
            const base = key.slice(0, -'.singular'.length);
            const existing = states.get(base) ?? { singular: false, plural: false };
            existing.singular = true;
            states.set(base, existing);
            continue;
        }
        if (key.endsWith('.plural')) {
            const base = key.slice(0, -'.plural'.length);
            const existing = states.get(base) ?? { singular: false, plural: false };
            existing.plural = true;
            states.set(base, existing);
        }
    }
    return Array.from(states.entries())
        .filter(([, state]) => state.singular && state.plural)
        .map(([base]) => base)
        .sort((a, b) => a.localeCompare(b));
};

const quoteStringLiteral = (value: string): string => {
    const escaped = value.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r/g, '\\r').replace(/\n/g, '\\n');
    return `'${escaped}'`;
};

const formatUnionType = (typeName: string, values: string[]): string => {
    if (!values.length) {
        return `export type ${typeName} = never;\n`;
    }
    return `export type ${typeName} = ${values.map((value) => quoteStringLiteral(value)).join(' | ')};\n`;
};

export { detectPluralBaseKeys, flattenLeafStringKeys, formatUnionType, isObject, normalizeTranslations };
export type { JsonValue };
