/* SoAI - Logs ZIP download response contract [frontend/assets/ts/core/api/contracts/systemLogsDownloadContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { decodeBufferedFileResponse } from '@core/api/contracts/downloadContracts.ts';
import type { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';

export const decodeLogsExportResponse = (value: ApiResponsePayload): BufferedApiResponse => {
    const response = decodeBufferedFileResponse(value);
    const contentType = response.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase();
    const disposition = response.headers.get('content-disposition') ?? '';
    if (contentType !== 'application/zip' || !/^attachment\s*(?:;|$)/i.test(disposition)) {
        throw new APIError(0, 'Logs download requires a ZIP attachment.', { code: 'logs_export_response' });
    }
    return response;
};
