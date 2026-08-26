/* SoAI - Shared realtime internals [frontend/assets/ts/core/realtime/streammanager/internals.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requirePerformanceNow } from '@core/environment/public.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { ApiServiceInterface, BundleDefinition, ResourceConfig, ResourceSnapshot, ResourceStatus, StateServiceInterface, StreamManagerDependencies } from '@core/realtime/streammanager/types.ts';
import { telemetry } from '@core/telemetry/service.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isArray, isFiniteNumber, isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { FulfilledResult } from '@core/types/streamTypes.ts';

const emitStreamEvent = (stage: string, data: Record<string, JsonValue | null> = {}, severity: 'info' | 'warn' | 'error' = 'info'): void => {
    telemetry.emit({ module: 'StreamManager', stage, severity, message: stage, data });
};

type StateServiceInterfaceCandidate = Partial<StateServiceInterface>;
type ApiServiceInterfaceCandidate = Partial<ApiServiceInterface> & {
    system?: Partial<ApiServiceInterface['system']> | null;
};
type StreamManagerAuthCandidate = Partial<NonNullable<StreamManagerDependencies['auth']>>;
type StreamManagerDependenciesCandidate = Partial<StreamManagerDependencies> & {
    apiClient?: ApiServiceInterfaceCandidate | null;
    state?: StateServiceInterfaceCandidate | null;
    connectionState?: Partial<StreamManagerDependencies['connectionState']> | null;
    auth?: StreamManagerAuthCandidate | null;
};

const isStateServiceInterface = (value: StateServiceInterfaceCandidate | JsonValue | null | undefined): value is StateServiceInterface => {
    if (!isObject(value) || isArray(value)) return false;
    return 'getTabState' in value && isFunction(value.getTabState) && 'setTabState' in value && isFunction(value.setTabState);
};

const isApiServiceInterface = (value: ApiServiceInterfaceCandidate | JsonValue | null | undefined): value is ApiServiceInterface => {
    if (!isObject(value) || isArray(value)) return false;
    const system = 'system' in value ? value.system : null;
    if (!isObject(system) || isArray(system)) return false;
    return 'logs' in system && isFunction(system.logs) && 'request' in value && isFunction(value.request);
};

const isAuthManagerContract = (value: StreamManagerAuthCandidate | JsonValue | null | undefined): boolean => {
    if (!isObject(value) || isArray(value)) {
        return false;
    }
    return 'isAuthenticated' in value && typeof value.isAuthenticated === 'boolean' && 'onLogin' in value && isFunction(value.onLogin);
};

const isStreamManagerDependencies = (value: StreamManagerDependenciesCandidate | JsonValue | null | undefined): value is StreamManagerDependencies => {
    if (!isObject(value) || isArray(value)) {
        return false;
    }
    const apiClient = 'apiClient' in value ? value.apiClient : null;
    if (!isObject(apiClient) || !isApiServiceInterface(apiClient)) {
        return false;
    }
    const state = 'state' in value ? value.state : null;
    if (!isObject(state) || !isStateServiceInterface(state)) {
        return false;
    }
    const connectionState = 'connectionState' in value ? value.connectionState : null;
    if (!isObject(connectionState) || isArray(connectionState) || !('onChange' in connectionState) || !isFunction(connectionState.onChange)) {
        return false;
    }
    const auth = 'auth' in value ? value.auth : null;
    if (auth === null) {
        return true;
    }
    return isObject(auth) && isAuthManagerContract(auth);
};

const identity = <T>(value: T): T => value;

const RESOURCE_STATUS_SET: ReadonlySet<string> = new Set(['initializing', 'unavailable', 'ready', 'recovering', 'disconnected', 'error']);

const isResourceStatusValue = (value: JsonValue | null | undefined): value is ResourceStatus => isString(value) && RESOURCE_STATUS_SET.has(value);

const isResourceSnapshot = (value: JsonValue | ResourceSnapshot | null | undefined): value is ResourceSnapshot => {
    if (!isObject(value)) return false;
    const snapshot = value;
    const name = 'name' in snapshot ? snapshot.name : null;
    const status = 'status' in snapshot ? snapshot.status : null;
    if (!isString(name) || !isResourceStatusValue(status)) {
        return false;
    }
    const updatedAt = 'updatedAt' in snapshot ? snapshot.updatedAt : null;
    if (updatedAt !== null && updatedAt !== undefined && !isFiniteNumber(updatedAt)) {
        return false;
    }
    return true;
};

const cloneSnapshot = (snapshot: JsonValue | ResourceSnapshot | null | undefined, name: string): ResourceSnapshot => {
    if (isResourceSnapshot(snapshot)) {
        return {
            name,
            value: snapshot.value,
            status: snapshot.status,
            updatedAt: snapshot.updatedAt ?? null,
            error: snapshot.error instanceof Error || isObject(snapshot.error) ? snapshot.error : null
        };
    }
    const candidate = isObject(snapshot) ? snapshot : null;
    const valueCandidate = candidate && hasOwn(candidate, 'value') ? candidate['value'] : snapshot;
    const resolvedValue = isJsonValue(valueCandidate) ? valueCandidate : null;
    const statusCandidate = candidate ? candidate['status'] : null;
    const resolvedStatus: ResourceStatus = isResourceStatusValue(statusCandidate) ? statusCandidate : 'unavailable';
    const resolvedUpdatedAt = candidate && isFiniteNumber(candidate['updated_at']) ? Number(candidate['updated_at']) : null;
    const candidateError = candidate ? candidate['error'] : null;
    const resolvedError = candidateError instanceof Error || (candidateError && isObject(candidateError)) ? candidateError : null;
    return {
        name,
        value: resolvedValue === undefined ? null : resolvedValue,
        status: resolvedStatus,
        updatedAt: resolvedUpdatedAt,
        error: resolvedError
    };
};

const getNow = requirePerformanceNow();

const resolveDeferredInitializationTimeoutMs = (options: { deferTimeoutMs?: number } | undefined): number | null => {
    const raw = options?.deferTimeoutMs;
    if (!isFiniteNumber(raw) || raw <= 0) {
        return null;
    }
    return Math.floor(raw);
};

const toBundleList = (bundle: BundleDefinition | null): string[] => (bundle?.resources ? Object.values(bundle.resources) : []);

const normalizeMaintenanceReason = (reason: string | null | undefined): string | null => toTrimmedString(reason) || null;

const filterFulfilled = (results: Array<PromiseSettledResult<JsonValue | null>>): Array<JsonValue | null> => results.filter((entry): entry is FulfilledResult<JsonValue | null> => entry.status === 'fulfilled').map((entry) => entry.value);

const RESOURCE_CONFIG_KEYS: Array<keyof ResourceConfig> = ['autoStart', 'fetch', 'normalize', 'transform', 'skipUnchangedTransform', 'websocketOnly'];

export { RESOURCE_CONFIG_KEYS, RESOURCE_STATUS_SET, cloneSnapshot, emitStreamEvent, filterFulfilled, getNow, identity, isApiServiceInterface, isResourceSnapshot, isResourceStatusValue, isStateServiceInterface, isStreamManagerDependencies, normalizeMaintenanceReason, resolveDeferredInitializationTimeoutMs, toBundleList };
