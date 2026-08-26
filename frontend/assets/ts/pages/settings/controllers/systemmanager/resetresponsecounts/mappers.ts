/* SoAI - Settings system reset response count parsing [frontend/assets/ts/pages/settings/controllers/systemmanager/resetresponsecounts/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readNonNegativeIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import { isPlainObject } from '@core/typeGuards.ts';

const readResetResponseCount = (value: ApiResponsePayload, owner: string, key: string): number => {
    const payload = requireJsonResponsePayload(value, owner);
    if (!isPlainObject(payload)) {
        throw new Error(`${owner} response must be an object`);
    }
    const count = readNonNegativeIntegerOrNullValue(payload[key]);
    if (count === null) {
        throw new Error(`${owner} response field "${key}" must be a non-negative integer`);
    }
    return count;
};

export { readResetResponseCount };
