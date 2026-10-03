/* SoAI - Models feature model search result parsing [frontend/assets/ts/features/models/search/modelSearchResults.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { readOptionalStringValue } from '@core/types/payloadValueReaders.ts';
import type { ModelSearchResult, ModelSearchResults } from '@features/models/search/modelSearchTypes.ts';

const parseModelSearchResult = (value: JsonValue, index: number): ModelSearchResult => {
    if (!isJsonObject(value)) throw new TypeError(`Model search result[${String(index)}] must be an object`);
    const result: ModelSearchResult = {};
    const id = readOptionalStringValue(value['id'], `Model search result[${String(index)}].id`);
    const name = readOptionalStringValue(value['name'], `Model search result[${String(index)}].name`);
    const summary = readOptionalStringValue(value['summary'], `Model search result[${String(index)}].summary`);
    const source = readOptionalStringValue(value['source'], `Model search result[${String(index)}].source`);
    const type = readOptionalStringValue(value['type'], `Model search result[${String(index)}].type`);
    const variants = value['variants'];
    if (variants !== undefined && variants !== null && !isJsonArray(variants)) throw new TypeError(`Model search result[${String(index)}].variants must be an array when provided`);
    if (id !== undefined) result.id = id;
    if (name !== undefined) result.name = name;
    if (summary !== undefined) result.summary = summary;
    if (source !== undefined) result.source = source;
    if (type !== undefined) result.type = type;
    if (isJsonArray(variants)) result.variants = [...variants];
    return result;
};

const parseModelSearchResults = (value: JsonValue | null | undefined): ModelSearchResults => {
    if (!isJsonArray(value)) return [];
    return value.map(parseModelSearchResult);
};

export { parseModelSearchResults };
