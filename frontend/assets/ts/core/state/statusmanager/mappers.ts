/* SoAI - Shared state mappers [frontend/assets/ts/core/state/statusmanager/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { hasFunctionProperty, hasOwn, isObject, isString } from '@core/typeGuards.ts';
import type { StatusInput } from '@core/state/statusTypes.ts';
import type { StreamManager } from '@core/state/statusmanager/contracts.ts';
import type { SnapshotValue } from '@core/state/statusmanager/internalContracts.ts';

const readStatusPrimitive = (value: JsonValue | undefined): string | number | null => {
    if (isString(value)) {
        const trimmed = value.trim();
        return trimmed ? trimmed : null;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value;
    }
    return null;
};

const readStatusFromPayload = (payload: JsonValue | undefined): StatusInput => {
    if (payload === null) {
        return null;
    }
    if (payload === undefined) {
        return undefined;
    }
    if (isString(payload)) {
        return payload;
    }
    if (typeof payload === 'number' && Number.isFinite(payload)) {
        return payload;
    }
    if (!isObject(payload)) {
        return null;
    }
    const rawStatus = payload['status'];
    const status = readStatusPrimitive(rawStatus);
    if (status !== null) {
        return status;
    }
    const state = payload['state'];
    const stateStatus = readStatusPrimitive(state);
    if (stateStatus !== null) {
        return stateStatus;
    }
    const value = payload['value'];
    const valueStatus = readStatusPrimitive(value);
    if (valueStatus !== null) {
        return valueStatus;
    }
    return payload;
};

const isStreamManager = <T>(value: T): value is T & StreamManager => {
    const record = isObject(value) ? value : null;
    if (!record) return false;
    if (!('resources' in record) || !('subscriptions' in record)) return false;
    const resources = record.resources;
    const subscriptions = record.subscriptions;
    return isObject(resources) && hasFunctionProperty(resources, 'getResource') && isObject(subscriptions) && hasFunctionProperty(subscriptions, 'subscribeResourceState');
};

const readSnapshotValue = (snapshot: { value?: SnapshotValue } | JsonValue | undefined): SnapshotValue => {
    if (!snapshot || !isObject(snapshot) || !hasOwn(snapshot, 'value')) {
        return undefined;
    }
    const raw = snapshot['value'];
    if (raw === null) {
        return null;
    }
    if (raw === undefined) {
        return undefined;
    }
    if (isString(raw)) {
        return raw;
    }
    if (typeof raw === 'number' && Number.isFinite(raw)) {
        return raw;
    }
    if (isObject(raw)) {
        return raw;
    }
    return undefined;
};

export { isStreamManager, readStatusFromPayload, readStatusPrimitive, readSnapshotValue };
