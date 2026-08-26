/* SoAI - Shared runtime environment validation [frontend/assets/ts/core/runtimeenv/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import { getEventHub } from '@core/environment/public.ts';
import { getStateManager } from '@core/state/public.ts';
import { hasFunctionProperties, isFunction, isRecordLike } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { BroadcastChannelInterface, EventHubInterface, StateManagerInterface, StreamManagerInterface } from '@core/runtimeenv/internalContracts.ts';

type RuntimeEnvGuardCandidate = BroadcastChannelInterface | EventHubInterface | JsonValue | StateManagerInterface | StreamManagerInterface | null | undefined;

const checkMethods = <T>(object: T, methods: readonly string[]): boolean => {
    return isRecordLike(object) && hasFunctionProperties(object, methods);
};

const isStateManagerInterface = (value: RuntimeEnvGuardCandidate): value is StateManagerInterface => checkMethods(value, ['snapshotTabState', 'setTabState']);

export const ensureStreamManager = (): StreamManagerInterface => {
    const streamManager = getStreamRuntime();
    if (!isRecordLike(streamManager.resources) || !checkMethods(streamManager.resources, ['ensureReady', 'startAuto', 'ensureResourceStarted']) || !isRecordLike(streamManager.subscriptions) || !checkMethods(streamManager.subscriptions, ['subscribeBundle'])) {
        throw new Error('Stream manager is unavailable');
    }
    return streamManager;
};

export const ensureStateManager = (): StateManagerInterface => {
    const stateManager = getStateManager();
    if (!isStateManagerInterface(stateManager)) {
        throw new Error('State manager must expose state accessors');
    }
    return stateManager;
};

export const ensureEventHubAvailable = (): EventHubInterface => {
    const hub = getEventHub();
    if (!isFunction(hub.addEventListener) || !isFunction(hub.removeEventListener)) {
        throw new Error('Event hub is unavailable');
    }
    return hub;
};

export const isBroadcastChannelInterface = (value: RuntimeEnvGuardCandidate): value is BroadcastChannelInterface => {
    if (!isRecordLike(value) || !('postMessage' in value) || !isFunction(value.postMessage) || !('close' in value) || !isFunction(value.close)) {
        return false;
    }
    return ('addEventListener' in value && isFunction(value.addEventListener)) || 'onmessage' in value;
};
