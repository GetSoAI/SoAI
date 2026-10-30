/* SoAI - Buffered download response contract [frontend/assets/ts/core/api/contracts/downloadContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';

const decodeBufferedFileResponse = (value: ApiResponsePayload): BufferedApiResponse => {
    if (!(value instanceof BufferedApiResponse)) throw new TypeError('File download response must be buffered.');
    return value;
};

export { decodeBufferedFileResponse };
