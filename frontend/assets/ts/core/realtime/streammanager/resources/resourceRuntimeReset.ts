/* SoAI - Resource-owner reset and disposal transitions [frontend/assets/ts/core/realtime/streammanager/resources/resourceRuntimeReset.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceEntry } from '@core/realtime/streammanager/types.ts';
import { hasResourceLiveDemand } from '@core/realtime/streammanager/resources/resourceActivationPolicy.ts';

const resetResourceRuntime = (resources: ReadonlyMap<string, ResourceEntry>, clearValues: boolean, clearListeners = false): void => {
    for (const resource of resources.values()) {
        if (clearListeners) {
            resource.listeners.clear();
            resource.reconciliationUnsubscribe?.();
            resource.reconciliationUnsubscribe = null;
            resource.reconciler.dispose();
            continue;
        }
        resource.reconciler.reset({ preserveValue: !clearValues });
        resource.reconciler.setLiveDemand(hasResourceLiveDemand(resource));
    }
};

export { resetResourceRuntime };
