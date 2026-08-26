/* SoAI - Shared API authenticated download [frontend/assets/ts/core/api/authenticatedDownload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import { sanitizeDownloadFilename, triggerDownloadLink } from '@core/primitives/download.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

const parseContentDispositionFilename = (headerValue: string | null): string | null => {
    const header = toTrimmedString(headerValue);
    if (!header) {
        return null;
    }
    const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match?.[1]) {
        try {
            return decodeURIComponent(utf8Match[1]);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('AuthenticatedDownload', 'Failed to decode UTF-8 filename from content-disposition header', runtimeError);
            return utf8Match[1];
        }
    }
    const quotedMatch = header.match(/filename=\"([^\"]+)\"/i);
    if (quotedMatch?.[1]) {
        return quotedMatch[1];
    }
    const plainMatch = header.match(/filename=([^;]+)/i);
    if (plainMatch?.[1]) {
        return plainMatch[1].trim();
    }
    return null;
};

const downloadAuthenticatedResponse = async <ResponseValue>(responseValue: ResponseValue, options: { filename?: string | null } = {}): Promise<string> => {
    let blob: Blob;
    let headers: Headers;
    if (responseValue instanceof BufferedApiResponse) {
        blob = responseValue.body;
        headers = responseValue.headers;
    } else if (typeof Response === 'function' && responseValue instanceof Response) {
        blob = await responseValue.blob();
        headers = responseValue.headers;
    } else {
        throw new Error('Authenticated download requires a response object');
    }
    const headerFilename = parseContentDispositionFilename(headers.get('content-disposition'));
    const fallbackFilename = typeof options.filename === 'string' ? toTrimmedString(options.filename) : '';
    const filenameCandidate = headerFilename || fallbackFilename;
    const filename = filenameCandidate ? sanitizeDownloadFilename(filenameCandidate, 'download') : '';
    const href = URL.createObjectURL(blob);
    try {
        triggerDownloadLink({
            href,
            ...(filename ? { filename } : { forceDownload: true }),
            revokeObjectUrl: true
        });
    } catch (error) {
        URL.revokeObjectURL(href);
        throw error;
    }
    return filename || '';
};

export { downloadAuthenticatedResponse };
