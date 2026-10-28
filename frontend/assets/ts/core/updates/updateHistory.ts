/* SoAI - Persisted update check results and completed installation timestamps [frontend/assets/ts/core/updates/updateHistory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageService } from '@core/storage/StorageService.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableTrimmedStringValue } from '@core/types/payloadValueReaders.ts';

const APPLICATION_UPDATE_HISTORY_KEY = 'updates_application_history';
const SYSTEM_UPDATE_HISTORY_KEY = 'updates_system_history';

type UpdateHistoryStorage = Pick<StorageService, 'get' | 'set' | 'flushPending'>;

interface UpdateHistory {
    checkedAtMs: number | null;
    resultAtMs: number | null;
    result: JsonObject | null;
    failure: string | null;
    updatedAtMs: number | null;
}

const readTimestamp = (value: JsonObject[string] | undefined, label: string): number | null => (value === null ? null : readRequiredNonNegativeIntegerValue(value, label));

const readUpdateHistory = (storage: UpdateHistoryStorage, key: string): UpdateHistory => {
    const value = storage.get(key, null);
    if (value === null) return { checkedAtMs: null, resultAtMs: null, result: null, failure: null, updatedAtMs: null };
    const record = requireRecord(value, 'Update history');
    if (record['schemaVersion'] !== 1) throw new Error('Unsupported update history format. Reload with a compatible SoAI version.');
    const result = record['result'];
    if (result !== null && !isJsonObject(result)) throw new TypeError('Update history result must be an object or null.');
    const history: UpdateHistory = {
        checkedAtMs: readTimestamp(record['checkedAtMs'], 'Update history.checkedAtMs'),
        resultAtMs: readTimestamp(record['resultAtMs'], 'Update history.resultAtMs'),
        result,
        failure: readNullableTrimmedStringValue(record['failure'], 'Update history.failure'),
        updatedAtMs: readTimestamp(record['updatedAtMs'], 'Update history.updatedAtMs')
    };
    if (history.failure !== null && history.checkedAtMs === null) throw new TypeError('Update history failure requires a check timestamp.');
    if ((history.result === null) !== (history.resultAtMs === null) || (history.resultAtMs !== null && (history.checkedAtMs === null || history.resultAtMs > history.checkedAtMs))) throw new TypeError('Update history timestamps do not match the saved result.');
    return history;
};

const saveUpdateCheck = async (storage: UpdateHistoryStorage, key: string, value: { checkedAtMs: number; result: JsonObject | null; failure: string | null }): Promise<UpdateHistory> => {
    readRequiredNonNegativeIntegerValue(value.checkedAtMs, 'Update history.checkedAtMs');
    if (value.result === null && value.failure === null) throw new TypeError('An update check requires a result or failure.');
    const previous = readUpdateHistory(storage, key);
    if (previous.checkedAtMs !== null && value.checkedAtMs < previous.checkedAtMs) {
        await storage.flushPending();
        return previous;
    }
    const history: UpdateHistory = {
        ...previous,
        checkedAtMs: value.checkedAtMs,
        resultAtMs: value.result === null ? previous.resultAtMs : value.checkedAtMs,
        result: value.result ?? previous.result,
        failure: value.failure
    };
    storage.set(key, { schemaVersion: 1, ...history });
    await storage.flushPending();
    return history;
};

const saveCompletedUpdate = async (storage: UpdateHistoryStorage, key: string, updatedAtMs: number): Promise<void> => {
    readRequiredNonNegativeIntegerValue(updatedAtMs, 'Update history.updatedAtMs');
    const previous = readUpdateHistory(storage, key);
    if (previous.updatedAtMs !== null && updatedAtMs <= previous.updatedAtMs) {
        await storage.flushPending();
        return;
    }
    storage.set(key, { schemaVersion: 1, ...previous, updatedAtMs });
    await storage.flushPending();
};

export { APPLICATION_UPDATE_HISTORY_KEY, SYSTEM_UPDATE_HISTORY_KEY, readUpdateHistory, saveCompletedUpdate, saveUpdateCheck };
export type { UpdateHistory, UpdateHistoryStorage };
