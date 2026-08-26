/* SoAI - Shared normalization primitives [frontend/assets/ts/core/normalize.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const ensureArray = <T>(value: T | T[] | null | undefined): T[] => {
    if (Array.isArray(value)) return value;
    if (value === null || value === undefined) return [];
    return [value];
};

const ensureArrayFiltered = <T>(value: T | T[] | null | undefined): NonNullable<T>[] => {
    const arr = ensureArray(value);
    return arr.filter((item): item is NonNullable<T> => item !== null && item !== undefined);
};

const toTrimmedString = <T>(value: T): string => (typeof value === 'string' ? value.trim() : '');

const toString = <T>(value: T): string => (value === null || value === undefined ? '' : String(value));

const toTrimmedStringOrNull = <T>(value: T): string | null => {
    const trimmed = toTrimmedString(value);
    return trimmed || null;
};

const toUpperCase = <T>(value: T): string => (typeof value === 'string' ? value.toUpperCase() : '');

const toLowerCase = <T>(value: T): string => (typeof value === 'string' ? value.toLowerCase() : '');

const toTrimmedUpper = <T>(value: T): string => (typeof value === 'string' ? value.trim().toUpperCase() : '');

const toTrimmedLower = <T>(value: T): string => (typeof value === 'string' ? value.trim().toLowerCase() : '');

const splitTrimmedList = (value: string, separator: string | RegExp): string[] => {
    return value
        .split(separator)
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0);
};

const trimStringList = (values: readonly string[]): string[] => {
    return values.map((value) => value.trim()).filter((value) => value.length > 0);
};

const uniqueStringsPreserveOrder = (values: readonly string[]): string[] => {
    const normalized: string[] = [];
    const seen = new Set<string>();
    for (const value of values) {
        if (!seen.has(value)) {
            seen.add(value);
            normalized.push(value);
        }
    }
    return normalized;
};

const uniqueSortedStrings = (values: readonly string[], locale: string): string[] => {
    return uniqueStringsPreserveOrder([...values].sort((left, right) => left.localeCompare(right, locale)));
};

export { ensureArray, ensureArrayFiltered, splitTrimmedList, toTrimmedString, toString, toTrimmedStringOrNull, toUpperCase, toLowerCase, toTrimmedUpper, toTrimmedLower, trimStringList, uniqueSortedStrings, uniqueStringsPreserveOrder };
