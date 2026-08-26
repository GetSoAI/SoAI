/* SoAI - Shared data offset pagination [frontend/assets/ts/core/data/offsetPagination.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readNullableNonNegativeIntegerValue, readRequiredNonNegativeIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { hasOwn } from '@core/typeGuards.ts';

interface OffsetPaginationMetadata {
    limit: number;
    offset: number;
    hasMore: boolean;
    nextOffset: number | null;
}

const readOffsetPaginationMetadata = (record: JsonObject, label: string): OffsetPaginationMetadata => {
    if (!hasOwn(record, 'next_offset')) {
        throw new Error(`${label} next_offset must be a non-negative integer or null`);
    }
    return {
        limit: readRequiredPositiveIntegerValue(record['limit'], `${label} limit`),
        offset: readRequiredNonNegativeIntegerValue(record['offset'], `${label} offset`),
        hasMore: readRequiredBooleanValue(record['has_more'], `${label} has_more`),
        nextOffset: readNullableNonNegativeIntegerValue(record['next_offset'], `${label} next_offset`)
    };
};

export { readOffsetPaginationMetadata };
export type { OffsetPaginationMetadata };
