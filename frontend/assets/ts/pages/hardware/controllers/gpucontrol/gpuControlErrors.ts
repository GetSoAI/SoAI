/* SoAI - Hardware page GPU control errors [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlErrors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { extractErrorCode } from '@core/errors/coerce.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';

const CONTROL_BACKEND_MISSING_FRAGMENT = 'no supported control backend';

export const resolveGpuApiErrorCode = (error: Error): string | null => {
    return extractErrorCode(error);
};

const textContainsMissingControlBackend = (value: string): boolean => value.toLowerCase().includes(CONTROL_BACKEND_MISSING_FRAGMENT);

const arrayContainsMissingControlBackend = (values: readonly JsonValue[]): boolean => {
    for (const value of values) {
        if (containsMissingControlBackend(value)) {
            return true;
        }
    }
    return false;
};

const objectContainsMissingControlBackend = (value: Record<string, JsonValue>): boolean => {
    for (const candidate of Object.values(value)) {
        if (containsMissingControlBackend(candidate)) {
            return true;
        }
    }
    return false;
};

const containsMissingControlBackend = (value: JsonValue): boolean => {
    if (isString(value)) {
        return textContainsMissingControlBackend(value);
    }
    if (isArray(value)) {
        return arrayContainsMissingControlBackend(value);
    }
    if (isObject(value)) {
        return objectContainsMissingControlBackend(value);
    }
    return false;
};

export const isGpuControlBackendMissingError = (error: Error): boolean => {
    if (textContainsMissingControlBackend(error.message)) {
        return true;
    }
    if (!isObject(error)) {
        return false;
    }
    return containsMissingControlBackend(error.message);
};
