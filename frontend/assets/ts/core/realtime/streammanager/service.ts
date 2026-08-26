/* SoAI - Shared realtime stream manager service [frontend/assets/ts/core/realtime/streammanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneSnapshot } from '@core/realtime/streammanager/internals.ts';
import type { BundleDefinition, BundleHandlers, ResourceEntry, ResourceSnapshot, StateServiceInterface, StreamSafeCallback, StreamSafeCallbackArgument } from '@core/realtime/streammanager/types.ts';
import { telemetry } from '@core/telemetry/service.ts';
import { isFunction, isPlainObject } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';

const publishQueueDepthMetric = (resources: Map<string, ResourceEntry>, source: string): number => {
    let queueDepth = 0;
    resources.forEach((resource) => {
        if (resource.reconciler.reconciling || resource.status !== 'ready') {
            queueDepth += 1;
        }
    });
    telemetry.publishMetric('stream.queueDepth', queueDepth, { source });
    return queueDepth;
};

const defineBundle = (bundlePrefix: string, bundles: Map<string, BundleDefinition>, name: string, config: Partial<BundleDefinition> & { resources: Record<string, string> }): BundleDefinition => {
    const definition: BundleDefinition = {
        name,
        stateKey: config.stateKey || `${bundlePrefix}${name}`,
        resources: { ...config.resources },
        streams: Array.isArray(config.streams) ? config.streams.slice() : []
    };
    bundles.set(name, definition);
    return definition;
};

const cacheBundleSnapshotInState = (stateService: StateServiceInterface, definition: BundleDefinition, resourceName: string, snapshot: ResourceSnapshot): void => {
    const tabState = stateService.getTabState(definition.stateKey);
    const currentRecord: JsonObject = isJsonObject(tabState) ? tabState : {};
    stateService.setTabState(definition.stateKey, {
        ...currentRecord,
        [resourceName]: toJsonCompatibleValue(cloneSnapshot(snapshot, resourceName))
    });
};

type UnsubscribeTarget = (() => void) | { unsubscribe?: () => void; close?: () => void } | string | null | undefined;

const callSafe = (callback: StreamSafeCallback | null | undefined, inputArguments: StreamSafeCallbackArgument[], onError: (error: Error) => void): void => {
    if (!isFunction(callback)) {
        return;
    }
    try {
        callback(...inputArguments);
    } catch (error) {
        const runtimeError = ensureError(error);
        onError(runtimeError);
    }
};

const deliverBundleSnapshot = (definition: BundleDefinition, alias: string, resourceName: string, snapshot: ResourceSnapshot, handlers: BundleHandlers, safeCall: (callback: StreamSafeCallback | null | undefined, ...inputArguments: StreamSafeCallbackArgument[]) => void): void => {
    const payload = snapshot.value;
    safeCall(handlers.aliases?.[alias], payload);
    safeCall(handlers.onSnapshot, {
        bundle: definition.name,
        alias,
        resource: resourceName,
        snapshot: cloneSnapshot(snapshot, resourceName)
    });
};

const runUnsubscribeTarget = (target: UnsubscribeTarget, onError: (error: Error) => void): void => {
    if (!target) {
        return;
    }
    try {
        if (isFunction(target)) {
            target();
            return;
        }
        const record = isPlainObject(target) ? target : null;
        if (record && isFunction(record['unsubscribe'])) {
            record['unsubscribe']();
            return;
        }
        if (record && isFunction(record['close'])) {
            record['close']();
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        onError(runtimeError);
    }
};

export { cacheBundleSnapshotInState, callSafe, defineBundle, deliverBundleSnapshot, publishQueueDepthMetric, runUnsubscribeTarget };
export type { UnsubscribeTarget };
