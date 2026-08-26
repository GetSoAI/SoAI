/* SoAI - Shared realtime hash signature [frontend/assets/ts/core/realtime/streammanager/hashSignature.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn, isObject } from '@core/typeGuards.ts';

const SIGNATURE_MAX_DEPTH = 100;
const SIGNATURE_CIRCULAR_MARKER = 9;
const SIGNATURE_OMITTED_MARKER = 10;
const SIGNATURE_MAX_STRING_CHARS = 2048;
const SIGNATURE_MAX_ARRAY_ITEMS = 128;
const SIGNATURE_MAX_OBJECT_KEYS = 128;
const SIGNATURE_OBJECT_KEY_PREFIX_ITEMS = Math.floor(SIGNATURE_MAX_OBJECT_KEYS / 2);
const SIGNATURE_OBJECT_KEY_SUFFIX_ITEMS = SIGNATURE_MAX_OBJECT_KEYS - SIGNATURE_OBJECT_KEY_PREFIX_ITEMS;

const resolveBoundedSampleRanges = (total: number, limit: number): Array<{ start: number; end: number }> => {
    if (limit <= 0 || total <= 0) {
        return [];
    }
    if (total <= limit) {
        return [{ start: 0, end: total }];
    }
    const prefixLength = Math.floor(limit / 2);
    const suffixLength = limit - prefixLength;
    return [
        { start: 0, end: prefixLength },
        { start: total - suffixLength, end: total }
    ];
};

const hashBoundedString = (hashValue: (value: number) => void, hashString: (str: string) => void, value: string): void => {
    hashValue(value.length);
    if (value.length <= SIGNATURE_MAX_STRING_CHARS) {
        hashString(value);
        return;
    }
    const prefixLength = Math.floor(SIGNATURE_MAX_STRING_CHARS / 2);
    const suffixLength = SIGNATURE_MAX_STRING_CHARS - prefixLength;
    hashString(value.slice(0, prefixLength));
    hashValue(SIGNATURE_OMITTED_MARKER);
    hashValue(value.length - SIGNATURE_MAX_STRING_CHARS);
    hashString(value.slice(value.length - suffixLength));
};

const hashSampledObjectEntries = <TValue>(hashString: (str: string) => void, hashValue: (value: number) => void, traverse: <TChild>(value: TChild, depth: number) => void, value: TValue, depth: number): void => {
    const leadingEntries: Array<[string, TValue[keyof TValue]]> = [];
    const trailingEntries: Array<[string, TValue[keyof TValue]]> = [];
    let keyCount = 0;
    for (const key in value) {
        if (!hasOwn(value, key)) {
            continue;
        }
        const entry: [string, TValue[keyof TValue]] = [key, value[key]];
        keyCount += 1;
        if (leadingEntries.length < SIGNATURE_OBJECT_KEY_PREFIX_ITEMS) {
            leadingEntries.push(entry);
            continue;
        }
        trailingEntries.push(entry);
        if (trailingEntries.length > SIGNATURE_OBJECT_KEY_SUFFIX_ITEMS) {
            trailingEntries.shift();
        }
    }
    hashValue(8);
    hashValue(keyCount);
    for (const [key, child] of leadingEntries) {
        hashString(key);
        traverse(child, depth + 1);
    }
    if (keyCount > SIGNATURE_MAX_OBJECT_KEYS) {
        hashValue(SIGNATURE_OMITTED_MARKER);
        hashValue(keyCount - SIGNATURE_MAX_OBJECT_KEYS);
    }
    for (const [key, child] of trailingEntries) {
        hashString(key);
        traverse(child, depth + 1);
    }
};

const computeHashSignature = <TValue>(value: TValue): number => {
    let hash = 5381;
    const visited = new WeakSet<WeakKey>();

    const hashValue = (value: number): void => {
        hash = ((hash << 5) + hash + value) | 0;
    };

    const hashString = (str: string): void => {
        for (let characterIndex = 0; characterIndex < str.length; characterIndex++) {
            hashValue(str.charCodeAt(characterIndex));
        }
    };

    const traverse = <TCurrentValue>(value: TCurrentValue, depth: number): void => {
        if (value === null) {
            hashValue(0);
            return;
        }
        if (value === undefined) {
            hashValue(1);
            return;
        }

        if (typeof value === 'boolean') {
            hashValue(value ? 3 : 2);
            return;
        }
        if (typeof value === 'number') {
            hashValue(4);
            hashString(String(value));
            return;
        }
        if (typeof value === 'string') {
            hashValue(5);
            hashBoundedString(hashValue, hashString, value);
            return;
        }
        if (typeof value !== 'object') {
            hashValue(6);
            hashString(String(value));
            return;
        }

        if (!isObject(value)) {
            hashValue(6);
            hashString(String(value));
            return;
        }

        const objectReference = value;
        if (visited.has(objectReference)) {
            hashValue(SIGNATURE_CIRCULAR_MARKER);
            return;
        }
        if (depth >= SIGNATURE_MAX_DEPTH) {
            hashValue(SIGNATURE_CIRCULAR_MARKER);
            return;
        }
        visited.add(objectReference);

        if (Array.isArray(value)) {
            hashValue(7);
            hashValue(value.length);
            const ranges = resolveBoundedSampleRanges(value.length, SIGNATURE_MAX_ARRAY_ITEMS);
            for (const range of ranges) {
                for (let index = range.start; index < range.end; index += 1) {
                    traverse(value[index], depth + 1);
                }
            }
            if (value.length > SIGNATURE_MAX_ARRAY_ITEMS) {
                hashValue(SIGNATURE_OMITTED_MARKER);
                hashValue(value.length - SIGNATURE_MAX_ARRAY_ITEMS);
            }
            return;
        }

        hashSampledObjectEntries(hashString, hashValue, traverse, objectReference, depth);
    };

    traverse(value, 0);
    return hash >>> 0;
};

const formatHashSignature = <TValue>(value: TValue): string => String(computeHashSignature(value));

export { computeHashSignature, formatHashSignature };
