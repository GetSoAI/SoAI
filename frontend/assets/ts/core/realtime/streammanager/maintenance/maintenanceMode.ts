/* SoAI - Resource-owner maintenance entry [frontend/assets/ts/core/realtime/streammanager/maintenance/maintenanceMode.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeMaintenanceReason } from '@core/realtime/streammanager/internals.ts';
import type { ResourceEntry, StreamManagerMaintenanceState } from '@core/realtime/streammanager/types.ts';
import { isObject } from '@core/typeGuards.ts';

interface EnterMaintenanceModeOptions {
    reason: string | null;
    resources: Map<string, ResourceEntry>;
}

const enterMaintenanceMode = (options: EnterMaintenanceModeOptions): StreamManagerMaintenanceState => {
    if (!isObject(options)) throw new Error('enterMaintenanceMode requires options');
    const reason = normalizeMaintenanceReason(options.reason);
    const activeResources: string[] = [];
    for (const resource of options.resources.values()) {
        if (resource.status !== 'unavailable' || resource.reconciler.reconciling) activeResources.push(resource.name);
        resource.reconciler.enterMaintenance(reason ?? 'maintenance');
    }
    return { active: true, reason, resources: activeResources };
};

export { enterMaintenanceMode };
export type { EnterMaintenanceModeOptions };
