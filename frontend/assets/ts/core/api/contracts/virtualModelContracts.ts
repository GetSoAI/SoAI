/* SoAI - Shared frontend API contract boundary virtual model contracts [frontend/assets/ts/core/api/contracts/virtualModelContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredEnumValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { decodeSuccessfulMutationResponse, type SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';

type VirtualModelStrategy = 'load_balancing' | 'failover';

interface VirtualModelConstituent {
    universalId: string;
    parameters: JsonObject;
}

interface VirtualModelRequestConstituent {
    universalId: string;
    parameters?: JsonObject;
}

interface VirtualModelResponse {
    name: string;
    strategy: VirtualModelStrategy;
    models: VirtualModelConstituent[];
    createdAtMs: number;
    lastModifiedAtMs: number;
    isEnabled: boolean;
}

interface VirtualModelCreateRequest {
    name: string;
    strategy: VirtualModelStrategy;
    models: VirtualModelRequestConstituent[];
}

interface VirtualModelUpdateRequest {
    strategy?: VirtualModelStrategy;
    models?: VirtualModelRequestConstituent[];
}

const decodeVirtualModelConstituent = (value: JsonValue, label: string): VirtualModelConstituent => {
    const record = requireRecord(value, label);
    return {
        universalId: readRequiredTrimmedString(record, 'universal_id', `${label}.universal_id`),
        parameters: requireRecord(record['parameters'], `${label}.parameters`)
    };
};

const decodeVirtualModelRequestConstituent = (value: JsonValue, label: string): VirtualModelRequestConstituent => {
    const record = requireRecord(value, label);
    const universalId = readRequiredTrimmedString(record, 'universal_id', `${label}.universal_id`);
    if (!('parameters' in record)) {
        return { universalId };
    }
    return { universalId, parameters: requireRecord(record['parameters'], `${label}.parameters`) };
};

const decodeRequestModels = (value: JsonValue | undefined, label: string): VirtualModelRequestConstituent[] => {
    if (!Array.isArray(value)) {
        throw new TypeError(`${label} must be an array.`);
    }
    return value.map((model, index) => decodeVirtualModelRequestConstituent(model, `${label}[${String(index)}]`));
};

const decodeVirtualModelCreateRequest = (value: JsonObject): VirtualModelCreateRequest => ({
    name: readRequiredTrimmedString(value, 'name', 'Virtual model create request.name'),
    strategy: readRequiredEnumValue(value['strategy'], 'Virtual model create request.strategy', ['load_balancing', 'failover']),
    models: decodeRequestModels(value['models'], 'Virtual model create request.models')
});

const decodeVirtualModelUpdateRequest = (value: JsonObject): VirtualModelUpdateRequest => {
    const request: VirtualModelUpdateRequest = {};
    if ('strategy' in value) {
        request.strategy = readRequiredEnumValue(value['strategy'], 'Virtual model update request.strategy', ['load_balancing', 'failover']);
    }
    if ('models' in value) {
        request.models = decodeRequestModels(value['models'], 'Virtual model update request.models');
    }
    if (request.strategy === undefined && request.models === undefined) {
        throw new TypeError('Virtual model update request must include strategy or models.');
    }
    return request;
};

const decodeVirtualModelResponse = (value: ApiResponsePayload | JsonValue, label: string = 'Virtual model response'): VirtualModelResponse => {
    const record = requireRecord(value, label);
    const models = record['models'];
    if (!Array.isArray(models)) {
        throw new TypeError(`${label}.models must be an array.`);
    }
    return {
        name: readRequiredTrimmedString(record, 'name', `${label}.name`),
        strategy: readRequiredEnumValue(record['strategy'], `${label}.strategy`, ['load_balancing', 'failover']),
        models: models.map((model, index) => decodeVirtualModelConstituent(model, `${label}.models[${String(index)}]`)),
        createdAtMs: readRequiredNonNegativeIntegerValue(record['created_at_ms'], `${label}.created_at_ms`),
        lastModifiedAtMs: readRequiredNonNegativeIntegerValue(record['last_modified_at_ms'], `${label}.last_modified_at_ms`),
        isEnabled: readRequiredBooleanValue(record['is_enabled'], `${label}.is_enabled`)
    };
};

const decodeVirtualModelListResponse = (value: ApiResponsePayload): VirtualModelResponse[] => {
    if (!Array.isArray(value)) {
        throw new TypeError('Virtual model list response must be an array.');
    }
    return value.map((model, index) => decodeVirtualModelResponse(model, `Virtual model list response[${String(index)}]`));
};

const decodeRoutingMutationResponse = (value: ApiResponsePayload): SuccessfulMutationResponse => decodeSuccessfulMutationResponse(value, 'Routing mutation response');

const serializeVirtualModelConstituent = (model: VirtualModelRequestConstituent): JsonObject => {
    const serialized: JsonObject = { 'universal_id': model.universalId };
    if (model.parameters !== undefined) serialized['parameters'] = model.parameters;
    return serialized;
};

const serializeVirtualModelCreateRequest = (request: VirtualModelCreateRequest): JsonObject => ({
    name: request.name,
    strategy: request.strategy,
    models: request.models.map(serializeVirtualModelConstituent)
});

const serializeVirtualModelUpdateRequest = (request: VirtualModelUpdateRequest): JsonObject => {
    const serialized: JsonObject = {};
    if (request.strategy !== undefined) serialized['strategy'] = request.strategy;
    if (request.models !== undefined) serialized['models'] = request.models.map(serializeVirtualModelConstituent);
    return serialized;
};

export { decodeRoutingMutationResponse, decodeVirtualModelCreateRequest, decodeVirtualModelListResponse, decodeVirtualModelResponse, decodeVirtualModelUpdateRequest, serializeVirtualModelCreateRequest, serializeVirtualModelUpdateRequest };
export type { VirtualModelConstituent, VirtualModelCreateRequest, VirtualModelRequestConstituent, VirtualModelResponse, VirtualModelStrategy, VirtualModelUpdateRequest };
