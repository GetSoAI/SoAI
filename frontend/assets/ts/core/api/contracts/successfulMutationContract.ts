/* SoAI - Successful API mutation response validation [frontend/assets/ts/core/api/contracts/successfulMutationContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';

interface SuccessfulMutationResponse {
    status: 'success';
    message: string;
}

const decodeSuccessfulMutationResponse = (value: ApiResponsePayload, label: string): SuccessfulMutationResponse => {
    const record = requireRecord(value, label);
    const status = readRequiredTrimmedString(record, 'status', `${label}.status`);
    if (status !== 'success') {
        throw new TypeError(`${label}.status must be success.`);
    }
    return { status, message: readRequiredTrimmedString(record, 'message', `${label}.message`) };
};

export { decodeSuccessfulMutationResponse };
export type { SuccessfulMutationResponse };
