/* SoAI - Frontend application entrypoint events [frontend/assets/ts/app/entrypoints/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getEventHub } from '@core/environment/public.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import { isPersistedPageHideEvent } from '@core/lifecycle/pageTermination.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';

const setupCleanupHandlers = (): void => {
    const unsubscribeAll = (event: Event): void => {
        if (isPersistedPageHideEvent(event) || windowIdentity.isDetachedContext()) return;
        getStreamRuntime().subscriptions.unsubscribeAll();
    };
    getEventHub().addEventListener('pagehide', unsubscribeAll, { passive: true });
};

export { setupCleanupHandlers };
