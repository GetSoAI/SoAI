/* SoAI - Shared types payload array readers [frontend/assets/ts/core/types/payloadArrayReaders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const readStringArrayEntries = <T>(value: T[], label: string): string[] => {
    const normalized: string[] = [];
    value.forEach((entry) => {
        if (typeof entry !== 'string') {
            throw new Error(`${label} must be an array of strings.`);
        }
        normalized.push(entry);
    });
    return normalized;
};

const readTrimmedStringArrayEntries = <T>(value: T[], label: string): string[] => {
    const normalized: string[] = [];
    value.forEach((entry) => {
        if (typeof entry !== 'string') {
            throw new Error(`${label} must be an array of strings.`);
        }
        const item = entry.trim();
        if (!item) {
            throw new Error(`${label} must be an array of non-empty strings.`);
        }
        normalized.push(item);
    });
    return normalized;
};

const readRequiredTrimmedStringArrayValue = <T>(value: T, label: string): string[] => {
    if (!Array.isArray(value)) {
        throw new Error(`${label} must be an array.`);
    }
    return readTrimmedStringArrayEntries(value, label);
};

const readRequiredStringArrayValue = <T>(value: T, label: string): string[] => {
    if (!Array.isArray(value)) {
        throw new Error(`${label} must be an array.`);
    }
    return readStringArrayEntries(value, label);
};

const readStringArrayOrEmptyValue = <T>(value: T, label: string): string[] => {
    if (value === null || value === undefined) {
        return [];
    }
    return readRequiredStringArrayValue(value, label);
};

const readTrimmedStringArrayOrEmptyValue = <T>(value: T, label: string): string[] => {
    if (value === null || value === undefined) {
        return [];
    }
    return readRequiredTrimmedStringArrayValue(value, label);
};

const filterStringArrayValue = <T>(value: T): string[] => {
    if (!Array.isArray(value)) {
        return [];
    }
    return value.filter((entry): entry is string => typeof entry === 'string');
};

const filterTrimmedStringArrayValue = <T>(value: T): string[] => {
    return filterStringArrayValue(value)
        .map((entry) => entry.trim())
        .filter(Boolean);
};

const filterNonEmptyStringArrayValue = <T>(value: T): string[] => {
    return filterStringArrayValue(value).filter((entry) => entry.trim().length > 0);
};

const readNullableStringArrayValue = <T>(value: T, label: string): string[] | null => {
    if (value === null || value === undefined) {
        return null;
    }
    if (!Array.isArray(value)) {
        throw new Error(`${label} must be an array of strings or null.`);
    }
    return readStringArrayEntries(value, label);
};

export { filterNonEmptyStringArrayValue, filterStringArrayValue, filterTrimmedStringArrayValue, readNullableStringArrayValue, readRequiredStringArrayValue, readRequiredTrimmedStringArrayValue, readStringArrayOrEmptyValue, readTrimmedStringArrayOrEmptyValue };
