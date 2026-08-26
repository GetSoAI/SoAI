/* SoAI - Resource decoder boundary and snapshot publication [frontend/assets/ts/core/realtime/streammanager/resources/resourceState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveRemoteTimestampMs } from '@core/realtime/streammanager/logSnapshotNormalization.ts';
import type { ResourceContext, ResourceEntry, ResourceSnapshot, ResourceUpdateOutcome, StreamSafeCallback, StreamSafeCallbackArgument } from '@core/realtime/streammanager/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFiniteNumber, isInstanceOf, isObject } from '@core/typeGuards.ts';
import type { WebSocketDispatchContext } from '@core/websocketclient/types.ts';

interface ResourceOptionRule {
    statuses: ReadonlySet<number>;
    match?: ((error: Error | JsonValue | null | undefined) => boolean) | undefined;
}

const getResourceSnapshot = (resource: ResourceEntry | null): ResourceSnapshot | null =>
    resource
        ? {
              name: resource.name,
              value: resource.value,
              status: resource.status,
              updatedAt: resource.updatedAt,
              error: resource.error
          }
        : null;

const notifyResourceUpdate = (options: { module: string; eventTarget: EventTarget; resource: ResourceEntry; updateType: string; raw?: JsonValue | null; safeCall: (callback: StreamSafeCallback | null | undefined, ...inputArguments: StreamSafeCallbackArgument[]) => void }): void => {
    const snapshot = getResourceSnapshot(options.resource);
    if (!snapshot) return;
    const context = options.raw === undefined ? { type: options.updateType } : { type: options.updateType, raw: options.raw };
    for (const listener of [...options.resource.listeners]) options.safeCall(listener, snapshot, context);
    try {
        options.eventTarget.dispatchEvent(new CustomEvent('update', { detail: { name: options.resource.name, state: snapshot, context } }));
    } catch (error) {
        errorHandler.debug(options.module, 'Resource update event dispatch failed', { resource: options.resource.name, error });
    }
};

const applyResourceError = (options: { module: string; name: string; error: Error | JsonValue | null | undefined; getResource(name: string): ResourceEntry | null; optionRules: Map<string, ResourceOptionRule> }): void => {
    const resource = options.getResource(options.name);
    if (!resource || resource.reconciler.snapshot.maintenance) return;
    const reconciler = resource.reconciler;
    const configurationRevision = resource.configurationRevision;
    const ownsError = (): boolean => resource.reconciler === reconciler && resource.configurationRevision === configurationRevision;
    const rule = options.optionRules.get(options.name);
    const errorObject = isObject(options.error) ? options.error : null;
    const statusCode = errorObject && 'status' in errorObject ? errorObject['status'] : null;
    if (!ownsError()) return;
    if (rule && isFiniteNumber(statusCode) && rule.statuses.has(statusCode) && isInstanceOf(options.error, APIError)) {
        try {
            if (!rule.match || rule.match(options.error)) {
                if (ownsError()) reconciler.markUnavailable('optional-resource-unavailable');
                return;
            }
        } catch (error) {
            if (!ownsError()) return;
            const matcherError = ensureError(error);
            errorHandler.warn(options.module, `Optional resource matcher failed for ${options.name}`, matcherError);
            if (ownsError()) reconciler.reportOperationalFailure(matcherError);
            return;
        }
    }
    const runtimeError = ensureError(options.error);
    if (ownsError()) reconciler.reportOperationalFailure(runtimeError);
};

const applyResourceUpdate = (options: { module: string; name: string; payload: JsonValue | null; updateType: string; raw: JsonValue | null; transportContext: WebSocketDispatchContext; getResource(name: string): ResourceEntry | null }): ResourceUpdateOutcome => {
    const resource = options.getResource(options.name);
    if (!resource || resource.reconciler.snapshot.maintenance) return 'ignored';
    const config = resource.config;
    const normalize = config.normalize;
    const transform = config.transform;
    const reconciler = resource.reconciler;
    const configurationRevision = resource.configurationRevision;
    const ownsUpdate = (): boolean => resource.config === config && config.normalize === normalize && config.transform === transform && resource.reconciler === reconciler && resource.configurationRevision === configurationRevision;
    try {
        const context: ResourceContext = {
            type: options.updateType,
            raw: options.raw,
            resource,
            previousValue: resource.value
        };
        const normalized = normalize(options.payload, context);
        if (!ownsUpdate()) return 'ignored';
        const transformed = transform(normalized, context);
        if (!ownsUpdate()) return 'ignored';
        if (config.skipUnchangedTransform === true && transformed === context.previousValue) return 'ignored';
        const applied = reconciler.commitPush(transformed, {
            transportEpoch: options.transportContext.connectionEpoch,
            receiveSequence: options.transportContext.receiveSequence,
            remoteTimestampMs: resolveRemoteTimestampMs(options.raw)
        });
        if (!applied || !ownsUpdate()) return 'ignored';
        return 'applied';
    } catch (error) {
        if (!ownsUpdate()) return 'ignored';
        const runtimeError = ensureError(error);
        errorHandler.warn(options.module, `Resource update rejected for ${options.name}`, runtimeError);
        reconciler.rejectPush(runtimeError);
        return 'rejected';
    }
};

export { applyResourceError, applyResourceUpdate, getResourceSnapshot, notifyResourceUpdate };
export type { ResourceOptionRule };
