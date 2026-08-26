/* SoAI - Model detail page contract boundary support [frontend/assets/ts/pages/modeldetail/contracts/modelDetailPageSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollapseController } from '@core/routing/pages/pagetypes/public.ts';
import type { StreamFinishedValue } from '@core/routing/pages/pagetypes/stream/types.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { createTtlCache, readTtlStorageValue, writeTtlStorageValue } from '@core/storage/ttlStorageCache.ts';
import { isFunction, isNullOrUndefined, isObject, isString, isThenable } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { ModelDetailParametersData } from '@pages/modeldetail/types.ts';

type ParametersData = ModelDetailParametersData;
const modelDetailLogger = createModuleLogger('ModelDetailPage', { defaultLevel: 'warn' });

interface StreamSubscription {
    unsubscribe?: () => void;
    close?: () => void;
}

interface StreamHandle {
    abort?: () => void;
    cancel?: () => void;
    finished: Promise<StreamFinishedValue>;
}

interface TestModalLogStreamHandle {
    close: () => void;
}

const isStreamHandle = (value: JsonValue | StreamHandle | null | undefined): value is StreamHandle => {
    if (!isObject(value)) {
        return false;
    }
    const finished = value['finished'];
    if (!isThenable(finished)) {
        return false;
    }
    const abort = value['abort'];
    const cancel = value['cancel'];
    if (!isNullOrUndefined(abort) && !isFunction(abort)) {
        return false;
    }
    if (!isNullOrUndefined(cancel) && !isFunction(cancel)) {
        return false;
    }
    return true;
};

const isTestModalLogStreamHandle = (value: JsonValue | TestModalLogStreamHandle | null | undefined): value is TestModalLogStreamHandle => {
    if (!isObject(value)) {
        return false;
    }
    return isFunction(value['close']);
};

const isCollapseController = (value: CollapseController | JsonValue | null | undefined): value is CollapseController => {
    if (!isObject(value)) {
        return false;
    }
    return isFunction(value['toggle']) && isFunction(value['isCollapsed']);
};

const isModelEntryMatch = (entry: JsonValue | null | undefined, modelId: string): boolean => {
    if (!isObject(entry)) {
        return false;
    }
    const id = entry['id'];
    const universalId = entry['universalId'];
    return (isString(id) && id === modelId) || (isString(universalId) && universalId === modelId);
};

const SNAPSHOT_CACHE_TTL_MS = 60000;
const MODEL_SNAPSHOT_CACHE = createTtlCache<ModelRecord | null>(SNAPSHOT_CACHE_TTL_MS);
const PARAMETER_SNAPSHOT_CACHE = createTtlCache<ParametersData | null>(SNAPSHOT_CACHE_TTL_MS);

const MODEL_STORAGE_PREFIX = 'soai.modelDetail.snapshot.';
const PARAMETER_STORAGE_PREFIX = 'soai.modelDetail.params.';

const readSnapshot = (prefix: string, key: string): JsonValue | null => readTtlStorageValue('sessionStorage', prefix + key, SNAPSHOT_CACHE_TTL_MS);

const writeSnapshot = (prefix: string, key: string, value: JsonValue | null): void => {
    writeTtlStorageValue('sessionStorage', prefix + key, value);
};

export { isCollapseController, isModelEntryMatch, isStreamHandle, isTestModalLogStreamHandle, MODEL_SNAPSHOT_CACHE, MODEL_STORAGE_PREFIX, PARAMETER_SNAPSHOT_CACHE, PARAMETER_STORAGE_PREFIX, readSnapshot, writeSnapshot };

export { modelDetailLogger };
export type { ParametersData, StreamHandle, StreamSubscription, TestModalLogStreamHandle };
