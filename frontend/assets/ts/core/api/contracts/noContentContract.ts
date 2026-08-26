/* SoAI - Frontend no-content HTTP response contract [frontend/assets/ts/core/api/contracts/noContentContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';

const decodeNoContentResponse = (value: ApiResponsePayload, label: string): void => {
    if (value !== undefined) throw new TypeError(`${label} must not contain a response body.`);
};

export { decodeNoContentResponse };
