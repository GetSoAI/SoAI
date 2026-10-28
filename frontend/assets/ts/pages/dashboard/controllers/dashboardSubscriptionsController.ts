/* SoAI - Dashboard page subscriptions controller [frontend/assets/ts/pages/dashboard/controllers/dashboardSubscriptionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { projectHardwareResourceObservation } from '@core/api/contracts/hardwareComponentObservationContracts.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { HARDWARE } from '@core/realtime/streammanager/resources/ids.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { DashboardLiveDataKey, DashboardSectionId } from '@pages/dashboard/controllers/dashboardLiveData.ts';
import { runDashboardSubscriptions } from '@pages/dashboard/services/service.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface DashboardSubscriptionsHost extends PageStreamingOwnerHost, PageDomOwnerHost {
    registerDashboardSubscription(subscription: () => void): void;
    handleLiveDataUpdate(type: DashboardLiveDataKey, payload: JsonValue): void;
    queueSectionRender(sectionId: DashboardSectionId): void;
}

class DashboardSubscriptionsController {
    readonly #resources = new ResourceTracker();
    #hardwareObservationTimer: number | null = null;
    #mainStateSubscription: (() => void) | null = null;
    #productSubscription: (() => void) | null = null;

    setup(host: DashboardSubscriptionsHost, subscribeProduct: ((listener: () => void) => () => void) | null): void {
        this.destroy();

        this.#mainStateSubscription = runDashboardSubscriptions({
            subscribeToData: (resource: string, handler: (payload: JsonValue) => void): (() => void) => {
                if (resource !== HARDWARE) return host.streaming.subscribeResourceValue(resource, handler);
                return host.streaming.subscribeResourceState(resource, (snapshot) => {
                    if (this.#hardwareObservationTimer !== null) this.#resources.clearTimeout(this.#hardwareObservationTimer);
                    const deliver = (): void => {
                        const value = projectHardwareResourceObservation(snapshot.value, snapshot.status, serverEpochMs());
                        if (value !== null) handler(value);
                    };
                    deliver();
                    if (snapshot.status !== 'ready' && snapshot.value !== null) {
                        const capabilities = isJsonObject(snapshot.value) ? snapshot.value['capabilities'] : null;
                        const interval = isJsonObject(capabilities) ? capabilities['monitoringIntervalMs'] : null;
                        this.#hardwareObservationTimer = this.#resources.setTimeout(deliver, 3 * (typeof interval === 'number' && interval > 0 ? interval : 1000));
                    }
                });
            },
            registerDashboardSubscription: (subscription: () => void): void => {
                host.registerDashboardSubscription(subscription);
            },
            handleLiveData: (type: DashboardLiveDataKey, payload: JsonValue): void => {
                host.handleLiveDataUpdate(type, payload);
            },
            queueStatusRender: (): void => host.queueSectionRender('status')
        });

        if (subscribeProduct) {
            this.#productSubscription = subscribeProduct((): void => host.queueSectionRender('productCapabilities'));
        }
    }

    destroy(): void {
        this.#resources.cleanup();
        this.#hardwareObservationTimer = null;
        if (this.#mainStateSubscription) {
            this.#mainStateSubscription();
            this.#mainStateSubscription = null;
        }
        if (this.#productSubscription) {
            this.#productSubscription();
            this.#productSubscription = null;
        }
    }
}

export { DashboardSubscriptionsController };
