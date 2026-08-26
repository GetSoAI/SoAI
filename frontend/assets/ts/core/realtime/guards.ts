/* SoAI - Shared realtime validation [frontend/assets/ts/core/realtime/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isFunction, isObject, isRecordLike } from '@core/typeGuards.ts';
import type { BundleResourceStreamManager, BundleSubscriptionStreamManager, ResourceLifecycleStreamManager, ResourceReadStreamManager, StreamBundleSubscription } from '@core/realtime/protocols.ts';

type StreamBundleSubscriptionCandidate = Partial<StreamBundleSubscription>;
interface BundleSubscriptionStreamManagerCandidate {
    subscribeToBundle?: CallableFunction;
}
interface ResourceReadStreamManagerCandidate {
    getResource?: CallableFunction;
}
interface ResourceLifecycleStreamManagerCandidate {
    ensureResourceStarted?: CallableFunction;
    subscribe?: CallableFunction;
    refresh?: CallableFunction;
}
type BundleResourceStreamManagerCandidate = BundleSubscriptionStreamManagerCandidate & ResourceReadStreamManagerCandidate;

const isStreamBundleSubscription = (value: StreamBundleSubscriptionCandidate | null): value is StreamBundleSubscription => {
    if (!isObject(value)) {
        return false;
    }
    const ready = 'ready' in value ? value.ready : undefined;
    const abort = 'abort' in value ? value.abort : undefined;
    const unsubscribe = 'unsubscribe' in value ? value.unsubscribe : undefined;
    if (ready !== undefined) {
        const readyRecord = isRecordLike(ready) ? ready : null;
        if (readyRecord === null || !hasFunctionProperty(readyRecord, 'then') || !hasFunctionProperty(readyRecord, 'catch')) {
            return false;
        }
    }
    if (abort !== undefined && !isFunction(abort)) {
        return false;
    }
    if (unsubscribe !== undefined && !isFunction(unsubscribe)) {
        return false;
    }
    return true;
};

const isBundleSubscriptionStreamManager = (value: BundleSubscriptionStreamManagerCandidate | null): value is BundleSubscriptionStreamManager => {
    return isObject(value) && 'subscribeToBundle' in value && isFunction(value.subscribeToBundle);
};

const isResourceReadStreamManager = (value: ResourceReadStreamManagerCandidate | null): value is ResourceReadStreamManager => {
    return isObject(value) && 'getResource' in value && isFunction(value.getResource);
};

const isBundleResourceStreamManager = (value: BundleResourceStreamManagerCandidate | null): value is BundleResourceStreamManager => {
    return isObject(value) && 'subscribeToBundle' in value && isFunction(value.subscribeToBundle) && 'getResource' in value && isFunction(value.getResource);
};

const isResourceLifecycleStreamManager = (value: ResourceLifecycleStreamManagerCandidate | null): value is ResourceLifecycleStreamManager => {
    return isObject(value) && 'ensureResourceStarted' in value && isFunction(value.ensureResourceStarted) && 'subscribe' in value && isFunction(value.subscribe) && 'refresh' in value && isFunction(value.refresh);
};

export { isBundleResourceStreamManager, isBundleSubscriptionStreamManager, isResourceLifecycleStreamManager, isResourceReadStreamManager, isStreamBundleSubscription };
