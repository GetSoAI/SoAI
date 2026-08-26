/* SoAI - Shared data paginated payload [frontend/assets/ts/core/data/paginatedPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readOffsetPaginationMetadata, type OffsetPaginationMetadata } from '@core/data/offsetPagination.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface PaginatedArrayPayload {
    items: readonly JsonValue[];
    metadata: OffsetPaginationMetadata;
}

const readPaginatedArrayPayload = <T>(payload: T, arrayKey: string, label: string): PaginatedArrayPayload => {
    if (!isJsonObject(payload)) {
        throw new Error(`${label} must be an object`);
    }
    const items = payload[arrayKey];
    if (!isJsonArray(items)) {
        throw new Error(`${label} must include an ${arrayKey} array`);
    }
    return {
        items,
        metadata: readOffsetPaginationMetadata(payload, label)
    };
};

export { readPaginatedArrayPayload };
