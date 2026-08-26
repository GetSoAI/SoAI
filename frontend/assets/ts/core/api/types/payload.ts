/* SoAI - Shared API payload [frontend/assets/ts/core/api/types/payload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';

type ApiResponsePayload = JsonValue | string | Blob | Response | BufferedApiResponse | undefined | void;

const isApiResponsePayload = <T>(value: T): value is T & ApiResponsePayload => {
    if (value === undefined) {
        return true;
    }
    if (isJsonValue(value)) {
        return true;
    }
    if (typeof Blob === 'function' && value instanceof Blob) {
        return true;
    }
    if (value instanceof BufferedApiResponse) {
        return true;
    }
    return typeof Response === 'function' && value instanceof Response;
};

export { isApiResponsePayload };
export type { ApiResponsePayload };
