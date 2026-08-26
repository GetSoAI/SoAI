/* SoAI - Shared client data hub validation [frontend/assets/ts/core/data/clientdatahub/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isArray, isBoolean, isNullOrUndefined, isNumber, isObject, isPlainObject, isString } from '@core/typeGuards.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import type { ResourceFieldValue, ResourceIncomingValue, ResourceItem } from '@core/data/clientdatahub/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

const logError = (message: string, detail?: Error | ResourceIncomingValue): void => {
    errorHandler?.error?.('ClientDataHub', message, detail);
};

const logDebug = (message: string, detail?: Error | ResourceIncomingValue): void => {
    errorHandler?.debug?.('ClientDataHub', message, detail);
};

const isResourceFieldValue = (value: ResourceIncomingValue): value is ResourceFieldValue => {
    return isNullOrUndefined(value) || isString(value) || isNumber(value) || isBoolean(value) || isArray(value) || isPlainObject(value);
};

const normalizeResourceItem = (entry: ResourceIncomingValue, context: string): ResourceItem => {
    if (!isPlainObject(entry)) {
        throw new TypeError(`${context} must be a plain object`);
    }
    const normalized: ResourceItem = {};
    for (const [key, value] of Object.entries(entry)) {
        if (!isResourceFieldValue(value)) {
            throw new TypeError(`${context}.${key} must be a resource field value`);
        }
        normalized[key] = value;
    }
    return normalized;
};

const normalizeResourceItemList = (value: ResourceIncomingValue, context: string): ResourceItem[] => {
    if (!isArray(value)) {
        return [];
    }
    const results: ResourceItem[] = [];
    for (let index = 0; index < value.length; index += 1) {
        const entry = value[index];
        if (!isPlainObject(entry)) {
            throw new TypeError(`${context}: item at index ${index} must be a plain object`);
        }
        results.push(normalizeResourceItem(entry, `${context}: item at index ${index}`));
    }
    return results;
};

const defaultTrackBy = (item: ResourceItem): string | null => {
    if (!item || !isObject(item)) {
        return null;
    }
    const itemObject = item;
    if (!isNullOrUndefined(itemObject['id'])) {
        return String(itemObject['id']);
    }
    if (!isNullOrUndefined(itemObject['name'])) {
        return String(itemObject['name']);
    }
    return null;
};

const defaultNormalize = (item: ResourceIncomingValue): ResourceItem => {
    return normalizeResourceItem(item, 'ClientDataHub resource item');
};

const defaultFingerprint = (item: ResourceItem): string => {
    if (isNullOrUndefined(item)) {
        return 'null';
    }
    if (isNumber(item) || isBoolean(item)) {
        return String(item);
    }
    if (isString(item)) {
        return item;
    }
    try {
        return JSON.stringify(item);
    } catch (error) {
        ensureError(error);
        return generateSecureId('fingerprint');
    }
};

const extractPayload = (payload: ResourceIncomingValue): ResourceIncomingValue => {
    if (payload && isObject(payload) && 'value' in payload) {
        return payload['value'];
    }
    return payload;
};

const normalizeResourceKey = (key: string): string => {
    if (isString(key) && key.trim()) {
        return key.trim();
    }
    throw new Error('ClientDataHub resource key must be a non-empty string');
};

export { defaultFingerprint, defaultNormalize, defaultTrackBy, extractPayload, logDebug, logError, normalizeResourceItem, normalizeResourceItemList, normalizeResourceKey };
