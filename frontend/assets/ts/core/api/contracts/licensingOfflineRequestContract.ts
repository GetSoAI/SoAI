/* SoAI - Licensing offline request download contract [frontend/assets/ts/core/api/contracts/licensingOfflineRequestContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';

const decodeLicensingOfflineRequest = (value: ApiResponsePayload): BufferedApiResponse => {
    if (!(value instanceof BufferedApiResponse)) throw new TypeError('Offline activation request must be a buffered response.');
    if (value.body.size > 65_536) throw new TypeError('Offline activation request exceeds the V1 limit.');
    const mediaType = value.headers.get('content-type')?.split(';', 1)[0]?.trim().toLowerCase();
    const revision = value.headers.get('x-soai-draft-revision');
    const digest = value.headers.get('x-soai-request-digest');
    const disposition = value.headers.get('content-disposition');
    const length = value.headers.get('content-length');
    if (mediaType !== 'application/vnd.soai.offline-activation-request+json') throw new TypeError('Offline activation request media type is invalid.');
    if (!revision || !/^(0|[1-9][0-9]*)$/.test(revision)) throw new TypeError('Offline activation request revision header is invalid.');
    if (!digest || !/^sha256:[a-f0-9]{64}$/.test(digest)) throw new TypeError('Offline activation request digest header is invalid.');
    if (disposition !== 'attachment; filename="soai-offline-activation-request-v1.json"') throw new TypeError('Offline activation request filename is invalid.');
    if (length !== null && Number(length) !== value.body.size) throw new TypeError('Offline activation request length is invalid.');
    return value;
};

export { decodeLicensingOfflineRequest };
