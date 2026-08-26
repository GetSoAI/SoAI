/* SoAI - Shared API configuration response contracts [frontend/assets/ts/core/api/contracts/configContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { isString } from '@core/typeGuards.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';

interface ConfigUpdateResponse {
    success: true;
    message: string;
}

const decodeConfigListResponse = (value: ApiResponsePayload): string[] => {
    if (!Array.isArray(value)) {
        throw new TypeError('Config list response must be an array.');
    }
    return value.map((entry, index) => {
        if (!isString(entry) || !entry.trim()) {
            throw new TypeError(`Config list response[${String(index)}] must be a non-empty string.`);
        }
        return entry.trim();
    });
};

const decodeConfigResponse = (value: ApiResponsePayload): OpaqueJsonObject => requireRecord(value, 'Config response');

const decodeConfigUpdateResponse = (value: ApiResponsePayload): ConfigUpdateResponse => {
    const record = requireRecord(value, 'Config update response');
    const success = readRequiredBooleanValue(record['success'], 'Config update response.success');
    if (!success) {
        throw new TypeError('Config update response.success must be true.');
    }
    return {
        success,
        message: readRequiredTrimmedString(record, 'message', 'Config update response.message')
    };
};

export { decodeConfigListResponse, decodeConfigResponse, decodeConfigUpdateResponse };
export type { ConfigUpdateResponse };
