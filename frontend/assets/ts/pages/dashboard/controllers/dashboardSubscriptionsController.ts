/* SoAI - Dashboard page subscriptions controller [frontend/assets/ts/pages/dashboard/controllers/dashboardSubscriptionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DashboardLiveDataKey, DashboardSectionId } from '@pages/dashboard/controllers/dashboardLiveData.ts';
import { optionalDashboardMainStateIndicator } from '@pages/dashboard/dom.ts';
import { runDashboardSubscriptions } from '@pages/dashboard/services/service.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface DashboardSubscriptionsHost extends PageStreamingOwnerHost, PageDomOwnerHost {
    registerDashboardSubscription(subscription: () => void): void;
    handleLiveDataUpdate(type: DashboardLiveDataKey, payload: JsonValue): void;
    queueSectionRender(sectionId: DashboardSectionId): void;
}

class DashboardSubscriptionsController {
    #mainStateSubscription: (() => void) | null = null;
    #productSubscription: (() => void) | null = null;

    setup(host: DashboardSubscriptionsHost, subscribeProduct: ((listener: () => void) => () => void) | null): void {
        this.destroy();

        this.#mainStateSubscription = runDashboardSubscriptions({
            subscribeToData: (resource: string, handler: (payload: JsonValue) => void): (() => void) => {
                return host.streaming.subscribeResourceValue(resource, handler);
            },
            registerDashboardSubscription: (subscription: () => void): void => {
                host.registerDashboardSubscription(subscription);
            },
            handleLiveData: (type: DashboardLiveDataKey, payload: JsonValue): void => {
                host.handleLiveDataUpdate(type, payload);
            },
            getMainStateIndicator: (): Element | null => {
                return optionalDashboardMainStateIndicator(host);
            }
        });

        if (subscribeProduct) {
            this.#productSubscription = subscribeProduct((): void => host.queueSectionRender('productCapabilities'));
        }
    }

    destroy(): void {
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
