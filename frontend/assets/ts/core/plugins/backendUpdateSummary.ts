/* SoAI - Disjoint plugin backend update snapshot groups [frontend/assets/ts/core/plugins/backendUpdateSummary.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasPluginBackendUpdate } from '@core/plugins/backendUpdates.ts';
import { PLUGIN_STATUS_BACKEND_UPDATING } from '@core/state/pluginStatus.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';

interface BackendUpdateSummary {
    available: PluginRecord[];
    updating: PluginRecord[];
    pending: PluginRecord[];
    failed: PluginRecord[];
}

const summarizePluginBackendUpdates = (plugins: readonly PluginRecord[], updatingPluginNames: ReadonlySet<string>): BackendUpdateSummary => {
    const summary: BackendUpdateSummary = { available: [], updating: [], pending: [], failed: [] };
    for (const plugin of plugins) {
        if (plugin.state === PLUGIN_STATUS_BACKEND_UPDATING || (plugin.name && updatingPluginNames.has(plugin.name))) {
            summary.updating.push(plugin);
        } else if (hasPluginBackendUpdate(plugin)) {
            summary.available.push(plugin);
        } else if (plugin.backendUpdate?.status === 'check_pending') {
            summary.pending.push(plugin);
        } else if (plugin.backendUpdate?.status === 'check_failed' || plugin.backendUpdate?.status === 'unavailable') {
            summary.failed.push(plugin);
        }
    }
    return summary;
};

export { summarizePluginBackendUpdates };
export type { BackendUpdateSummary };
