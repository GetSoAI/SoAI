/* SoAI - Decoded realtime model collection contract [frontend/assets/ts/core/models/decodedModelCollection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const decodeModel = (value: JsonValue): ModelData | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const id = value['id'];
    const name = value['name'];
    if (!isString(id) || id.trim().length === 0 || !isString(name) || name.trim().length === 0) {
        return null;
    }
    return { ...value, id, name };
};

const readDecodedModelCollection = (payload: JsonValue): ModelData[] | null => {
    if (!isJsonArray(payload)) {
        return null;
    }
    const models: ModelData[] = [];
    for (const entry of payload) {
        const model = decodeModel(entry);
        if (model === null) {
            return null;
        }
        models.push(model);
    }
    return models;
};

export { readDecodedModelCollection };
