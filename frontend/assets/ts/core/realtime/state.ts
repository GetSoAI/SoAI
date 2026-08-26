/* SoAI - Shared realtime state [frontend/assets/ts/core/realtime/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getStreamResources, getStreamSubscriptions } from '@core/realtime/streammanager/public.ts';
import { createModuleLogger, type ModuleLogger } from '@core/runtime/runtimeContext.ts';
import { isObject, isThenable, isString } from '@core/typeGuards.ts';

import type { OwnerState, StreamManagerInterface } from '@core/realtime/types.ts';

type RealtimeIdentifier = string | { id?: string | null; streamId?: string | null; connectionId?: string | null; identifier?: string | null; key?: string | null; name?: string | null } | null | undefined;

const log: ModuleLogger = createModuleLogger('Realtime', { defaultLevel: 'warn' });
const stateByOwner = new WeakMap<WeakKey, OwnerState>();

const ensureOwnerState = (owner: WeakKey): OwnerState => {
    const existing = stateByOwner.get(owner);
    if (existing) {
        return existing;
    }
    const created: OwnerState = { subscriptions: new Map() };
    stateByOwner.set(owner, created);
    return created;
};

const getOwnerState = (owner: WeakKey): OwnerState | null => stateByOwner.get(owner) ?? null;

const deleteOwnerState = (owner: WeakKey): void => {
    stateByOwner.delete(owner);
};

const selectStreamManager = (provided?: StreamManagerInterface | null): StreamManagerInterface | null => {
    const candidate = provided ?? getStreamSubscriptions();
    if (!candidate) {
        return null;
    }
    if (typeof candidate.subscribeResourceState !== 'function') {
        log('error', 'StreamManager does not expose resource-state subscriptions');
        return null;
    }
    if (typeof candidate.unsubscribe !== 'function') {
        log('warn', 'StreamManager is missing unsubscribe API; unsubscribe strings may fail');
    }
    return candidate;
};

const ensureManager = (): StreamManagerInterface => {
    const manager = selectStreamManager();
    if (!manager) {
        throw new Error('StreamManager unavailable');
    }
    return manager;
};

const ensureResourceStarted = (name: string): Promise<void> => {
    const result = getStreamResources().ensureResourceStarted(name);
    if (!isThenable(result)) {
        return Promise.resolve();
    }
    return Promise.resolve(result).then(() => undefined);
};

const normalizeIdentifier = (identifier: RealtimeIdentifier): string => {
    if (isString(identifier)) {
        const trimmed = identifier.trim();
        if (trimmed) {
            return trimmed;
        }
    }
    if (identifier && isObject(identifier)) {
        const candidates: ReadonlyArray<keyof Exclude<RealtimeIdentifier, string | null | undefined>> = ['id', 'streamId', 'connectionId', 'identifier', 'key', 'name'];
        const identifierRecord = identifier;
        for (const key of candidates) {
            const value = identifierRecord[key];
            if (isString(value) && value.trim()) {
                return value.trim();
            }
        }
    }
    throw new Error('Realtime unsubscribe requires a stream identifier');
};

export { ensureOwnerState, getOwnerState, deleteOwnerState, selectStreamManager, ensureManager, ensureResourceStarted, normalizeIdentifier };
export type { RealtimeIdentifier };
