/* SoAI - Frontend OpenAI model catalog contracts [frontend/assets/ts/core/api/contracts/openAiModelCatalogContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface OpenAiModelCatalogEntry {
    id: string;
    object: 'model';
    created: number;
    ownedBy: string;
    contextWindowTokens?: number | undefined;
    modalities?: string[] | undefined;
    openaiCapabilities?: JsonObject | undefined;
}

interface OpenAiModelCatalogResponse {
    object: 'list';
    data: OpenAiModelCatalogEntry[];
}

const OPENAI_MODEL_CATALOG_KEYS: ReadonlySet<string> = Object.freeze(new Set(['object', 'data']));
const OPENAI_MODEL_ENTRY_KEYS: ReadonlySet<string> = Object.freeze(new Set(['id', 'object', 'created', 'owned_by', 'context_window_tokens', 'modalities', 'openai_capabilities']));

const assertAllowedKeys = (value: JsonObject, allowed: ReadonlySet<string>, label: string): void => {
    for (const key of Object.keys(value)) if (!allowed.has(key)) throw new TypeError(`${label} contains unexpected key "${key}"`);
};

const decodeOpenAiModelCatalogEntry = (value: JsonValue, index: number): OpenAiModelCatalogEntry => {
    if (!isJsonObject(value)) throw new TypeError(`OpenAI model catalog entry ${String(index)} must be an object`);
    assertAllowedKeys(value, OPENAI_MODEL_ENTRY_KEYS, `OpenAI model catalog entry ${String(index)}`);
    const idValue = value['id'];
    const objectValue = value['object'];
    const createdValue = value['created'];
    const ownerValue = value['owned_by'];
    if (!isString(idValue) || !idValue.trim()) throw new TypeError(`OpenAI model catalog entry ${String(index)} must include a non-empty id`);
    if (objectValue !== 'model') throw new TypeError(`OpenAI model catalog entry ${String(index)} must include object="model"`);
    if (!isNonNegativeInteger(createdValue)) throw new TypeError(`OpenAI model catalog entry ${String(index)} must include a non-negative created timestamp`);
    if (!isString(ownerValue) || !ownerValue.trim()) throw new TypeError(`OpenAI model catalog entry ${String(index)} must include a non-empty owned_by`);
    const entry: OpenAiModelCatalogEntry = { id: idValue.trim(), object: 'model', created: createdValue, ownedBy: ownerValue.trim() };
    const contextWindowTokensValue = value['context_window_tokens'];
    if (contextWindowTokensValue !== undefined) {
        if (!isNonNegativeInteger(contextWindowTokensValue) || contextWindowTokensValue < 1) throw new TypeError(`OpenAI model catalog entry ${String(index)} context_window_tokens must be a positive integer`);
        entry.contextWindowTokens = contextWindowTokensValue;
    }
    const modalitiesValue = value['modalities'];
    if (modalitiesValue !== undefined) {
        if (!isJsonArray(modalitiesValue) || modalitiesValue.length === 0) throw new TypeError(`OpenAI model catalog entry ${String(index)} modalities must not be empty`);
        entry.modalities = modalitiesValue.map((item, modalityIndex) => {
            if (!isString(item) || !item.trim()) throw new TypeError(`OpenAI model catalog entry ${String(index)} modalities[${String(modalityIndex)}] must be a non-empty string`);
            return item.trim();
        });
    }
    const capabilitiesValue = value['openai_capabilities'];
    if (capabilitiesValue !== undefined) {
        if (!isJsonObject(capabilitiesValue)) throw new TypeError(`OpenAI model catalog entry ${String(index)} openai_capabilities must be an object`);
        entry.openaiCapabilities = capabilitiesValue;
    }
    return entry;
};

const decodeOpenAiModelCatalog = (payload: JsonValue): OpenAiModelCatalogResponse => {
    if (!isJsonObject(payload)) throw new TypeError('OpenAI model catalog payload must be an object');
    assertAllowedKeys(payload, OPENAI_MODEL_CATALOG_KEYS, 'OpenAI model catalog payload');
    if (payload['object'] !== 'list') throw new TypeError('OpenAI model catalog payload must include object="list"');
    const dataValue = payload['data'];
    if (!isJsonArray(dataValue)) throw new TypeError('OpenAI model catalog payload must include a data array');
    return { object: 'list', data: dataValue.map(decodeOpenAiModelCatalogEntry) };
};

const decodeOpenAiModel = (payload: ApiResponsePayload): OpenAiModelCatalogEntry => {
    if (!isJsonObject(payload)) throw new TypeError('OpenAI model response must be an object');
    return decodeOpenAiModelCatalogEntry(payload, 0);
};

export { decodeOpenAiModel, decodeOpenAiModelCatalog };
export type { OpenAiModelCatalogEntry, OpenAiModelCatalogResponse };
