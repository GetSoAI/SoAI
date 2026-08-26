/* SoAI - Frontend Restart Overlay Session Repository [frontend/assets/ts/features/overlays/restart/sessionRepository.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { createStorageTextAdapter } from '@core/storage/ttlStorageCache.ts';
import { isBoolean, isNonNegativeInteger, isObject, isPositiveInteger, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PersistentRestartOperationType, RestartOperationState, RestartSessionRepository, RestartSessionStorage } from '@features/overlays/restart/types.ts';

const RESTART_SESSION_STORAGE_KEY = 'soai.restart.operation.v1';
const PERSISTENT_OPERATION_TYPES: ReadonlySet<string> = new Set(['restart-application', 'system-reboot', 'system-shutdown', 'system-sleep', 'update-soai', 'restore-backup']);

const isPersistentRestartOperationType = (value: JsonValue | undefined): value is PersistentRestartOperationType => isString(value) && PERSISTENT_OPERATION_TYPES.has(value);

const decodeRestartOperationState = (value: JsonValue): RestartOperationState | null => {
    if (!isObject(value) || Object.keys(value).length !== 5) {
        return null;
    }
    const type = value['type'];
    const timestamp = value['timestamp'];
    const retry = value['retry'];
    const observeTransition = value['observeTransition'];
    const interruptionObserved = value['interruptionObserved'];
    if (!isPersistentRestartOperationType(type) || !isPositiveInteger(timestamp) || !isNonNegativeInteger(retry) || !isBoolean(observeTransition) || !isBoolean(interruptionObserved)) {
        return null;
    }
    return { type, timestamp, retry, observeTransition, interruptionObserved };
};

const createRestartSessionRepository = (storage: RestartSessionStorage = createStorageTextAdapter('sessionStorage')): RestartSessionRepository => {
    const clear = (): void => {
        storage.removeItem(RESTART_SESSION_STORAGE_KEY);
    };
    const read = (): RestartOperationState | null => {
        const rawValue = storage.getItem(RESTART_SESSION_STORAGE_KEY);
        if (rawValue === null) {
            return null;
        }
        let parsed: JsonValue;
        try {
            parsed = parseRequiredJsonText(rawValue);
        } catch (error) {
            errorHandler.debug('RestartSessionRepository', 'Removing malformed restart session state', ensureError(error));
            clear();
            return null;
        }
        const state = decodeRestartOperationState(parsed);
        if (!state) {
            clear();
            return null;
        }
        return state;
    };
    const save = (state: RestartOperationState): void => {
        const decoded = decodeRestartOperationState({ type: state.type, timestamp: state.timestamp, retry: state.retry, observeTransition: state.observeTransition, interruptionObserved: state.interruptionObserved });
        if (!decoded) {
            throw new Error('Restart operation state is invalid');
        }
        storage.setItem(RESTART_SESSION_STORAGE_KEY, JSON.stringify(decoded));
    };
    return { clear, read, save };
};

export { RESTART_SESSION_STORAGE_KEY, createRestartSessionRepository, decodeRestartOperationState, isPersistentRestartOperationType };
