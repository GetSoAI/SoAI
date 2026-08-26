/* SoAI - Shared primitives sort [frontend/assets/ts/core/primitives/sort.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export const normalizeSortFilterValue = (value: string | null | undefined, allowed: string[], defaultValue: string): string => {
    if (value === null || value === undefined) return defaultValue;
    const normalized = String(value).toLowerCase().trim();
    return allowed.includes(normalized) ? normalized : defaultValue;
};

export const resolveSortComparator = <T>(sortBy: string, defaultSort: string, comparators: Record<string, (firstValue: T, secondValue: T) => number>, context: string): ((firstValue: T, secondValue: T) => number) => {
    const key = sortBy || defaultSort;
    const comparator = comparators[key];
    if (!comparator) {
        throw new Error(`${context} is missing a sort comparator for key "${key}"`);
    }
    return comparator;
};
