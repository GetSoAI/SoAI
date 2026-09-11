/* SoAI - Plugins page state actions [frontend/assets/ts/pages/plugins/state/pluginsStateActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { disablePluginActionPath, enablePluginActionPath, stopPluginActionPath } from '@core/api/endpoints/uiPaths.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isPluginModelUnavailableStatus, PLUGIN_STATUS_DISABLED, PLUGIN_STATUS_INCOMPATIBLE, PLUGIN_STATUS_PERSISTENT_READY, PLUGIN_STATUS_STOPPED } from '@core/state/pluginStatus.ts';
import type { PluginCompatibilityOverrideResponse } from '@core/api/contracts/pluginManagementContracts.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { OptimisticOperation } from '@core/data/clientdatahub/types.ts';
import { normalizeResourceItem } from '@core/data/clientdatahub/guards.ts';

interface PluginsStateActionHost extends PageFeedbackOwnerHost {
    activeToggles: Set<string>;
    pendingToggleTargets: Map<string, boolean>;
    api: {
        system: {
            resetCircuitBreaker(pluginName: string): Promise<SuccessfulMutationResponse>;
        };
        plugins: {
            overrideIncompatibility(pluginName: string, override: boolean): Promise<PluginCompatibilityOverrideResponse>;
        };
    };
    catalogStore: {
        getPlugin(pluginName: string): PluginRecord | null;
        beginOptimisticOperation(operation: OptimisticOperation): void;
        hasPendingOptimisticOperation(pluginName: string): boolean;
    };
    runWithBoundary(scope: string, task: () => Promise<void>): Promise<void>;
    runPageTask<Result>(
        taskKey: string,
        task: () => Promise<Result>,
        options: {
            displayName: string;
        }
    ): Promise<Result | null>;
    runPluginTaskAction(
        taskKey: string,
        endpoint: string,
        options: {
            pluginName: string;
            displayName: string;
            onAccepted?: (taskId: string) => void;
        }
    ): Promise<Record<string, JsonValue> | null>;
    commitCatalogPlugin(plugin: ResourceIncomingValue): PluginRecord | null;
    rerenderPlugin(pluginName: string): void;
    isHardwareIncompatible(plugin: PluginRecord): boolean;
    canExecutePluginAction(plugin: PluginRecord, options?: { allowCompatibilityOverride?: boolean | undefined }): boolean;
    getPluginStatus(plugin: PluginRecord): string;
    isPluginPermanentlyDisabled(plugin: PluginRecord): boolean;
    notifyPluginIncompatible(plugin: PluginRecord): void;
    isPluginStoppable(plugin: PluginRecord): boolean;
}

const releaseLocalToggleAdmission = (host: PluginsStateActionHost, pluginName: string): void => {
    const releasedPendingTarget = host.pendingToggleTargets.delete(pluginName);
    const releasedActiveToggle = host.activeToggles.delete(pluginName);
    if (!releasedPendingTarget && !releasedActiveToggle) return;
    performance.mark(`soai-audit:local-clear:${pluginName}`);
    host.rerenderPlugin(pluginName);
};

const applyCompatibilityOverrideResponse = (host: PluginsStateActionHost, pluginName: string, sourcePlugin: PluginRecord, response: PluginCompatibilityOverrideResponse | null): PluginCompatibilityOverrideResponse => {
    if (!response || response.plugin !== pluginName) {
        throw new Error('Plugin compatibility override response did not include the requested plugin');
    }
    const current = host.catalogStore.getPlugin(pluginName) ?? sourcePlugin;
    const responseState = response.state;
    host.commitCatalogPlugin(
        toJsonCompatibleValue({
            ...current,
            state: responseState,
            isEnabled: !isPluginModelUnavailableStatus(responseState),
            incompatibility: response.incompatibility ?? null
        })
    );
    return response;
};

const setPluginCompatibilityOverride = async (host: PluginsStateActionHost, plugin: PluginRecord, override: boolean, event?: Event): Promise<void> =>
    host.runWithBoundary('plugins:setCompatibilityOverride', async (): Promise<void> => {
        const pluginName = toTrimmedString(plugin?.name);
        if (!pluginName || host.activeToggles.has(pluginName) || host.catalogStore.hasPendingOptimisticOperation(pluginName)) return;
        event?.stopPropagation();
        event?.preventDefault();
        const currentPlugin = host.catalogStore.getPlugin(pluginName) ?? plugin;
        const compatibility = currentPlugin.compatibility;
        if (!compatibility?.reason || compatibility.canOverride !== true) {
            host.notifyPluginIncompatible(currentPlugin);
            return;
        }
        if (Boolean(compatibility.isOverridden) === override) {
            host.rerenderPlugin(pluginName);
            return;
        }
        host.activeToggles.add(pluginName);
        const displayName = currentPlugin.displayName ?? currentPlugin.name ?? pluginName;
        const taskDisplayName = override ? i18n.t('plugins.actions.overridePlugin') : i18n.t('plugins.actions.disableOverride');
        try {
            const result = await host.runPageTask('plugins.setCompatibilityOverride', () => host.api.plugins.overrideIncompatibility(pluginName, override), {
                displayName: taskDisplayName
            });
            applyCompatibilityOverrideResponse(host, pluginName, currentPlugin, result);
            if (override) {
                host.feedback.show(i18n.t('plugins.notifications.overrideEnabled', { plugin: displayName }), 'success');
            } else {
                host.feedback.show(i18n.t('plugins.notifications.overrideDisabled', { plugin: displayName }), 'warning');
            }
        } finally {
            host.activeToggles.delete(pluginName);
            host.rerenderPlugin(pluginName);
        }
    });

const resetPluginCircuitBreaker = async (host: PluginsStateActionHost, plugin: PluginRecord, event?: Event): Promise<void> =>
    host.runWithBoundary('plugins:resetCircuitBreaker', async (): Promise<void> => {
        const pluginName = toTrimmedString(plugin?.name);
        if (!pluginName || host.activeToggles.has(pluginName)) return;
        event?.stopPropagation();
        event?.preventDefault();
        host.activeToggles.add(pluginName);
        const displayName = plugin.displayName ?? pluginName;
        const notification = i18n.t('plugins.notifications.circuitBreakerReset', { plugin: displayName });
        try {
            await host.runPageTask('plugins.resetCircuitBreaker', () => host.api.system.resetCircuitBreaker(pluginName), { displayName: notification });
            host.feedback.show(notification, 'success');
        } finally {
            host.activeToggles.delete(pluginName);
        }
    });

const togglePluginEnabledState = async (host: PluginsStateActionHost, plugin: PluginRecord, event?: Event): Promise<void> =>
    host.runWithBoundary('plugins:togglePluginEnabled', async (): Promise<void> => {
        const pluginName = toTrimmedString(plugin?.name);
        if (!pluginName || host.activeToggles.has(pluginName) || host.catalogStore.hasPendingOptimisticOperation(pluginName)) return;
        event?.stopPropagation();
        event?.preventDefault();
        const allowOverride = host.isHardwareIncompatible(plugin);
        if (!host.canExecutePluginAction(plugin, { allowCompatibilityOverride: allowOverride })) return;
        host.activeToggles.add(pluginName);
        const store = host.catalogStore;
        const currentPlugin = store.getPlugin(pluginName) ?? plugin;
        const status = host.getPluginStatus(currentPlugin);
        const isEnabled = currentPlugin.isEnabled ? true : currentPlugin.isEnabled === false ? false : status !== PLUGIN_STATUS_DISABLED && status !== PLUGIN_STATUS_INCOMPATIBLE;
        const action: 'disable' | 'enable' = isEnabled ? 'disable' : 'enable';
        const pendingToggleTarget = !isEnabled;
        const isDisable = action === 'disable';
        const taskDisplayName = isDisable ? i18n.t('plugins.notifications.pluginDisabled') : i18n.t('plugins.notifications.pluginEnabled');
        host.pendingToggleTargets.set(pluginName, pendingToggleTarget);
        host.rerenderPlugin(pluginName);
        try {
            if (!isDisable && allowOverride) {
                const result = await host.runPageTask('plugins.applyCompatibilityOverride', () => host.api.plugins.overrideIncompatibility(pluginName, true), {
                    displayName: i18n.t('plugins.actions.overridePlugin')
                });
                const overrideResponse = applyCompatibilityOverrideResponse(host, pluginName, currentPlugin, result);
                if (overrideResponse.state === PLUGIN_STATUS_STOPPED) {
                    host.feedback.show(i18n.t('plugins.notifications.pluginEnabled'), 'success');
                    return;
                }
            }
            const actionPath = isDisable ? disablePluginActionPath(pluginName) : enablePluginActionPath(pluginName);
            const taskResult = await host.runPluginTaskAction(`plugins.${isDisable ? 'disablePlugin' : 'enablePlugin'}`, actionPath, {
                pluginName: pluginName,
                displayName: taskDisplayName,
                onAccepted: (taskId): void => {
                    const desiredItem = normalizeResourceItem(
                        toJsonCompatibleValue({
                            ...(isDisable ? { state: PLUGIN_STATUS_DISABLED } : {}),
                            isEnabled: !isDisable
                        }),
                        'Plugin toggle optimistic projection'
                    );
                    host.catalogStore.beginOptimisticOperation({
                        operationId: taskId,
                        itemId: pluginName,
                        desiredItem,
                        acceptedTaskId: taskId
                    });
                    releaseLocalToggleAdmission(host, pluginName);
                }
            });
            if (!taskResult) {
                return;
            }
            host.feedback.show(isDisable ? i18n.t('plugins.notifications.pluginDisabled') : i18n.t('plugins.notifications.pluginEnabled'), isDisable ? 'warning' : 'success');
        } finally {
            releaseLocalToggleAdmission(host, pluginName);
        }
    });

const stopPluginProcess = async (host: PluginsStateActionHost, plugin: PluginRecord): Promise<void> => {
    if (!plugin?.name) return;
    if (host.isPluginPermanentlyDisabled(plugin)) {
        host.notifyPluginIncompatible(plugin);
        return;
    }
    if (!host.isPluginStoppable(plugin)) {
        if (host.getPluginStatus(plugin) === PLUGIN_STATUS_PERSISTENT_READY) {
            host.feedback.show(i18n.t('plugins.notifications.persistentNoStop'), 'warning');
        } else {
            host.feedback.show(i18n.t('plugins.notifications.notStoppable'), 'warning');
        }
        return;
    }
    const taskResult = await host.runPluginTaskAction('plugins.stopPlugin', stopPluginActionPath(plugin.name), {
        pluginName: plugin.name,
        displayName: i18n.t('plugins.notifications.pluginStopInProgress', { plugin: plugin.name })
    });
    if (taskResult) host.feedback.show(i18n.t('plugins.notifications.stopSuccess', { plugin: plugin.name }), 'success');
};

export { resetPluginCircuitBreaker, setPluginCompatibilityOverride, stopPluginProcess, togglePluginEnabledState };
export type { PluginsStateActionHost };
