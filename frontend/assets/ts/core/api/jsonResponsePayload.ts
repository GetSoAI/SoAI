/* SoAI - JSON API response payload narrowing [frontend/assets/ts/core/api/jsonResponsePayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';

const requireJsonResponsePayload = (payload: ApiResponsePayload, context: string): JsonValue => {
    if (payload === undefined) {
        throw new Error(`${context} response must include a JSON payload.`);
    }
    if (isJsonValue(payload)) {
        return payload;
    }
    throw new Error(`${context} response must be JSON.`);
};

export { requireJsonResponsePayload };
