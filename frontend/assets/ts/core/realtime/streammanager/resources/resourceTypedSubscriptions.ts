/* SoAI - Stable typed resource subscriptions [frontend/assets/ts/core/realtime/streammanager/resources/resourceTypedSubscriptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceStateListener } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import type { ResourceEntry, ResourceTypedSubscriber } from '@core/realtime/streammanager/types.ts';

const bindResourceTypedSubscription = (resource: ResourceEntry, subscriber: ResourceTypedSubscriber, immediate: boolean): void => {
    if (!subscriber.active) return;
    subscriber.bindingRevision += 1;
    const bindingRevision = subscriber.bindingRevision;
    subscriber.unsubscribeReconciler?.();
    subscriber.unsubscribeReconciler = null;
    const unsubscribe = resource.reconciler.subscribe(
        (snapshot): void => {
            if (!subscriber.active || subscriber.bindingRevision !== bindingRevision) return;
            const initial = subscriber.initial;
            subscriber.initial = false;
            subscriber.listener(snapshot, {
                type: snapshot.transitionType,
                transitionType: snapshot.transitionType,
                initial
            });
        },
        { immediate }
    );
    if (!subscriber.active || subscriber.bindingRevision !== bindingRevision) {
        unsubscribe();
        return;
    }
    subscriber.unsubscribeReconciler = unsubscribe;
};

const createResourceTypedSubscription = (resource: ResourceEntry, listener: ResourceStateListener): ResourceTypedSubscriber => {
    const subscriber: ResourceTypedSubscriber = {
        listener,
        initial: false,
        active: true,
        bindingRevision: 0,
        unsubscribeReconciler: null
    };
    resource.typedSubscribers.add(subscriber);
    return subscriber;
};

const rebindResourceTypedSubscriptions = (resource: ResourceEntry): void => {
    for (const subscriber of [...resource.typedSubscribers]) bindResourceTypedSubscription(resource, subscriber, true);
};

const removeResourceTypedSubscription = (resource: ResourceEntry, subscriber: ResourceTypedSubscriber): void => {
    if (!subscriber.active) return;
    subscriber.active = false;
    subscriber.bindingRevision += 1;
    resource.typedSubscribers.delete(subscriber);
    subscriber.unsubscribeReconciler?.();
    subscriber.unsubscribeReconciler = null;
};

export { bindResourceTypedSubscription, createResourceTypedSubscription, rebindResourceTypedSubscriptions, removeResourceTypedSubscription };
