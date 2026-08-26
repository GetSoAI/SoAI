/* SoAI - Plugins page rendering layer card renderer mapping [frontend/assets/ts/pages/plugins/rendering/cardrenderer/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ActionState, PluginCardData, PluginCardHost, PluginRecord } from '@pages/plugins/rendering/cardrenderer/types.ts';

function prepareCardData(host: PluginCardHost, plugin: PluginRecord): PluginCardData {
    const statusManager = host.status.presenter;
    const status = host.status.getPluginStatus(plugin);
    return {
        cardId: host.actions.getItemCardId(plugin),
        hardwareIncompatible: host.compatibility.isHardwareIncompatible(plugin),
        status,
        statusClass: statusManager.getCollectionStatusClass(status),
        statusLabel: statusManager.getDescription(status),
        statusBadgeClass: statusManager.getCollectionBadgeClass(status),
        circuitBreakerActive: host.compatibility.isCircuitBreakerActive(plugin),
        overrideRequired: host.compatibility.requiresCompatibilityOverride(plugin)
    };
}

function resolveActionState(host: PluginCardHost, plugin: PluginRecord, lockState: boolean): ActionState {
    const hasConfiguration = plugin.capabilities?.hasConfiguration ?? true;
    return {
        hasConfigAction: Boolean(hasConfiguration) && !lockState,
        hasCloneAction: host.actions.supportsPluginCloning?.(plugin) === true && !lockState && plugin?.isEnabled !== false
    };
}

export { prepareCardData, resolveActionState };
