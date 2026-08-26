/* SoAI - Shared types runtime collection guards [frontend/assets/ts/core/types/runtimeCollectionGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';

const isStringRecordValue = <T>(value: T): value is T & Record<string, string> => {
    return isJsonObject(value) && Object.values(value).every((entry) => typeof entry === 'string');
};

const isJsonObjectMapValue = <T>(value: T): value is T & Record<string, JsonObject> => {
    return isJsonObject(value) && Object.values(value).every(isJsonObject);
};

const isNonEmptyFiniteNumberArrayValue = <T>(value: T): value is T & readonly number[] => {
    return Array.isArray(value) && value.length > 0 && value.every((entry): entry is number => typeof entry === 'number' && Number.isFinite(entry));
};

export { isJsonObjectMapValue, isNonEmptyFiniteNumberArrayValue, isStringRecordValue };
