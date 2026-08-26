/* SoAI - Shared firstrun state [frontend/assets/ts/core/firstrun/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent } from '@core/environment/public.ts';
import type { FirstRunModalId, FirstRunModalStateEntry, FirstRunModalStateMap, FirstRunStateStorage, FirstRunStateStorageValue } from '@core/firstrun/protocols.ts';
import { isNumber, isObject } from '@core/typeGuards.ts';

const FIRST_RUN_MODAL_STORAGE_KEY = 'soai_first_run_modals';
const FIRST_RUN_MODAL_STATE_CHANGED_EVENT = 'soai:first-run-modal-state-changed';

const FIRST_RUN_MODAL_IDS: readonly FirstRunModalId[] = Object.freeze(['chatMemoryProfile', 'dashboardIntro', 'pluginsIntro']);

const isFirstRunModalId = (value: string): value is FirstRunModalId => {
    return FIRST_RUN_MODAL_IDS.some((candidate) => candidate === value);
};

const normalizeFirstRunModalStateEntry = (value: FirstRunStateStorageValue | undefined): FirstRunModalStateEntry | null => {
    if (!isObject(value)) {
        return null;
    }
    const statusValue = value['status'];
    const updatedAtValue = value['updated_at_ms'];
    if ((statusValue !== 'dismissed' && statusValue !== 'completed') || !isNumber(updatedAtValue) || !Number.isFinite(updatedAtValue)) {
        return null;
    }
    return {
        status: statusValue,
        updatedAtMs: updatedAtValue
    };
};

const normalizeFirstRunModalStateMap = (value: FirstRunStateStorageValue): FirstRunModalStateMap => {
    if (!isObject(value)) {
        return {};
    }
    const state: FirstRunModalStateMap = {};
    Object.entries(value).forEach(([key, entryValue]) => {
        if (!isFirstRunModalId(key)) {
            return;
        }
        const normalizedEntry = normalizeFirstRunModalStateEntry(entryValue);
        if (!normalizedEntry) {
            return;
        }
        state[key] = normalizedEntry;
    });
    return state;
};

const cloneFirstRunModalStateMap = (value: FirstRunModalStateMap): FirstRunModalStateMap => {
    const cloned: FirstRunModalStateMap = {};
    FIRST_RUN_MODAL_IDS.forEach((id) => {
        const entry = value[id];
        if (!entry) {
            return;
        }
        cloned[id] = {
            status: entry.status,
            updatedAtMs: entry.updatedAtMs
        };
    });
    return cloned;
};

const serializeFirstRunModalStateMap = (value: FirstRunModalStateMap): FirstRunStateStorageValue => {
    const serialized: FirstRunStateStorageValue = {};
    FIRST_RUN_MODAL_IDS.forEach((id) => {
        const entry = value[id];
        if (!entry) {
            return;
        }
        serialized[id] = {
            status: entry.status,
            'updated_at_ms': entry.updatedAtMs
        };
    });
    return serialized;
};

const readFirstRunModalStateMap = (storage: FirstRunStateStorage): FirstRunModalStateMap => {
    return normalizeFirstRunModalStateMap(storage.get(FIRST_RUN_MODAL_STORAGE_KEY, {}));
};

const writeFirstRunModalStateMap = (storage: FirstRunStateStorage, state: FirstRunModalStateMap): void => {
    const nextState = cloneFirstRunModalStateMap(state);
    storage.set(FIRST_RUN_MODAL_STORAGE_KEY, serializeFirstRunModalStateMap(nextState));
    dispatchCustomEvent(FIRST_RUN_MODAL_STATE_CHANGED_EVENT, { state: nextState });
};

const setFirstRunModalPending = (storage: FirstRunStateStorage, id: FirstRunModalId): FirstRunModalStateMap => {
    return setFirstRunModalsPending(storage, [id]);
};

const setFirstRunModalsPending = (storage: FirstRunStateStorage, ids: readonly FirstRunModalId[]): FirstRunModalStateMap => {
    const state = readFirstRunModalStateMap(storage);
    ids.forEach((id) => {
        delete state[id];
    });
    writeFirstRunModalStateMap(storage, state);
    return state;
};

const setFirstRunModalStatus = (storage: FirstRunStateStorage, id: FirstRunModalId, status: 'dismissed' | 'completed', updatedAtMs: number): FirstRunModalStateMap => {
    const state = readFirstRunModalStateMap(storage);
    state[id] = {
        status,
        updatedAtMs: updatedAtMs
    };
    writeFirstRunModalStateMap(storage, state);
    return state;
};

const setFirstRunModalDismissed = (storage: FirstRunStateStorage, id: FirstRunModalId, updatedAtMs: number): FirstRunModalStateMap => {
    return setFirstRunModalStatus(storage, id, 'dismissed', updatedAtMs);
};

const setFirstRunModalCompleted = (storage: FirstRunStateStorage, id: FirstRunModalId, updatedAtMs: number): FirstRunModalStateMap => {
    return setFirstRunModalStatus(storage, id, 'completed', updatedAtMs);
};

const isFirstRunModalPending = (state: FirstRunModalStateMap, id: FirstRunModalId): boolean => state[id] === undefined;

const readFirstRunModalStateStatus = (storage: FirstRunStateStorage, id: FirstRunModalId): 'pending' | 'dismissed' | 'completed' => {
    const entry = readFirstRunModalStateMap(storage)[id];
    if (!entry) {
        return 'pending';
    }
    return entry.status;
};

export { FIRST_RUN_MODAL_IDS, FIRST_RUN_MODAL_STATE_CHANGED_EVENT, FIRST_RUN_MODAL_STORAGE_KEY, cloneFirstRunModalStateMap, isFirstRunModalId, isFirstRunModalPending, normalizeFirstRunModalStateMap, readFirstRunModalStateMap, readFirstRunModalStateStatus, serializeFirstRunModalStateMap, setFirstRunModalCompleted, setFirstRunModalDismissed, setFirstRunModalPending, setFirstRunModalsPending, writeFirstRunModalStateMap };
