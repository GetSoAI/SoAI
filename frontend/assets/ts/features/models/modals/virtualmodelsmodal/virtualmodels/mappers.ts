/* SoAI - Virtual model modal mapping [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodels/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { isJsonArray, type JsonValue } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';
import type { ModelEntry, VirtualModelRecord } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';

const normalizeConstituentModelEntry = (value: JsonValue | null | undefined): ModelEntry => {
    if (!isObject(value)) {
        throw new TypeError('Virtual model constituent entry must be an object');
    }
    const universalId = readRequiredTrimmedStringValue(value['universalId'], 'Virtual model constituent universalId');
    return { universalId };
};

const normalizeVirtualModelRecord = (value: JsonValue | null | undefined): VirtualModelRecord => {
    if (!isObject(value)) {
        throw new TypeError('Virtual model entry must be an object');
    }
    const name = readRequiredTrimmedStringValue(value['name'], 'Virtual model name');
    const strategy = readRequiredTrimmedStringValue(value['strategy'], 'Virtual model strategy');
    const modelsRaw = value['models'];
    if (!isJsonArray(modelsRaw)) {
        throw new TypeError('Virtual model models must be an array');
    }
    const models = modelsRaw.map((entry) => normalizeConstituentModelEntry(entry));
    return { name, strategy, models };
};

const normalizeVirtualModelsPayload = (payload: JsonValue | null | undefined): VirtualModelRecord[] => {
    if (!isJsonArray(payload)) {
        throw new TypeError('Virtual models payload must be an array');
    }
    return payload.map((entry) => normalizeVirtualModelRecord(entry));
};

export { normalizeVirtualModelsPayload, normalizeVirtualModelRecord };
