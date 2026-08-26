/* SoAI - Shared frontend API contract boundary model operation contracts [frontend/assets/ts/core/api/contracts/modelOperationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface ModelAliasUpdateRequest {
    displayName?: string | null;
    description?: string | null;
}

interface ModelTaskAcceptedResponse {
    status: 'accepted';
    taskId: string;
}

interface ModelDiscoveryResponse {
    message: string;
}

const decodeModelTaskAcceptedResponse = (value: ApiResponsePayload): ModelTaskAcceptedResponse => {
    const label = 'Model task response';
    const record = requireRecord(value, label);
    const status = readRequiredTrimmedString(record, 'status', `${label}.status`);
    if (status !== 'accepted') {
        throw new TypeError(`${label}.status must be accepted.`);
    }
    return {
        status,
        taskId: readRequiredTrimmedString(record, 'task_id', `${label}.task_id`)
    };
};

const decodeModelDiscoveryResponse = (value: ApiResponsePayload): ModelDiscoveryResponse => {
    const record = requireRecord(value, 'Model discovery response');
    return {
        message: readRequiredTrimmedString(record, 'message', 'Model discovery response.message')
    };
};

const serializeModelAliasUpdateRequest = (request: ModelAliasUpdateRequest): JsonObject => {
    const serialized: JsonObject = {};
    if (request.displayName !== undefined) {
        serialized['display_name'] = request.displayName;
    }
    if (request.description !== undefined) {
        serialized['description'] = request.description;
    }
    return serialized;
};

export { decodeModelDiscoveryResponse, decodeModelTaskAcceptedResponse, serializeModelAliasUpdateRequest };
export type { ModelAliasUpdateRequest, ModelDiscoveryResponse, ModelTaskAcceptedResponse };
