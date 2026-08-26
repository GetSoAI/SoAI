/* SoAI - Frontend application entrypoint events [frontend/assets/ts/app/entrypoints/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getEventHub } from '@core/environment/public.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import { registerPageTerminationListeners } from '@core/lifecycle/pageTermination.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';

const setupCleanupHandlers = (): void => {
    registerPageTerminationListeners();
    const unsubscribeAll = (): void => {
        if (windowIdentity.isDetachedContext()) return;
        getStreamRuntime().subscriptions.unsubscribeAll();
    };
    getEventHub().addEventListener('beforeunload', unsubscribeAll, { passive: true });
};

export { setupCleanupHandlers };
