/* SoAI - Shared API normalizers [frontend/assets/ts/core/api/apiNormalizers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureArrayFiltered, toString, toTrimmedString } from '@core/normalize.ts';

type ModelsFilterInput = string | readonly string[] | Iterable<string> | null | undefined | void;

const entryProcessor = (entry: string): string => toTrimmedString(entry);

const normalizeNonEmptyString = <T>(value: T): string => {
    if (typeof value === 'string') return toTrimmedString(value);
    return value === null || value === undefined ? '' : toTrimmedString(toString(value));
};

const normalizeModelsFilter = (value: ModelsFilterInput): string[] | undefined => {
    if (value === null || value === undefined) return undefined;
    if (Array.isArray(value)) return ensureArrayFiltered(value.map(entryProcessor));
    if (typeof value === 'string') return ensureArrayFiltered(value.split(',').map(entryProcessor));
    return ensureArrayFiltered(Array.from(value, entryProcessor));
};

export { normalizeNonEmptyString, normalizeModelsFilter };
