/* SoAI - Plugins page control layer hosts [frontend/assets/ts/pages/plugins/controllers/hosts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { PluginsManagerHostCallbacks } from '@features/plugins/public.ts';
import type { PluginActionHost, PluginsStateActionDispatcher } from '@pages/plugins/controllers/contracts.ts';
import { PluginsDataController } from '@pages/plugins/controllers/dataController.ts';
import { PluginsOperationsController } from '@pages/plugins/controllers/operationsController.ts';
import { PluginsCompatibilityController } from '@pages/plugins/controllers/pluginsCompatibilityController.ts';

interface CreatePluginsActionHostDependencies {
    callbacks: PluginsManagerHostCallbacks;
    dataController: PluginsDataController;
    compatibilityController: PluginsCompatibilityController;
    operationsController: PluginsOperationsController;
    stateActions: PluginsStateActionDispatcher;
    prepareConfigModal(plugin: PluginRecord): void;
    openInstallBackendModal(plugin: PluginRecord): void;
    openManageBackendModal(plugin: PluginRecord): void;
    openCloneModal(plugin: PluginRecord): void;
    openPluginInfoModal(plugin: PluginRecord): void;
    navigateToModels(action: string, plugin: PluginRecord): boolean;
    dom: { getData(element: Element, key: string): string | null };
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
}

const trackPluginActionTask = (label: string, task: Promise<void>): void => {
    task.catch((error) => {
        errorHandler.error('PluginsPage', `Plugin action failed: ${label}`, ensureError(error));
    });
};

const createPluginsActionHost = (dependencies: CreatePluginsActionHostDependencies): PluginActionHost => {
    return {
        presentation: {
            updateProperty: dependencies.callbacks.updateProperty,
            toggleClassName: dependencies.callbacks.toggleClassName,
            dom: dependencies.dom,
            formatPluginName: (name: string): string => dependencies.dataController.formatPluginName(name),
            showNotification: dependencies.showNotification
        },
        policy: {
            deletePlugin: (pluginName: string): void => {
                trackPluginActionTask('deletePlugin', dependencies.operationsController.deletePlugin(pluginName));
            },
            prepareConfigModal: (plugin: PluginRecord): void => dependencies.prepareConfigModal(plugin),
            isHardwareIncompatible: (plugin: PluginRecord): boolean => dependencies.dataController.isHardwareIncompatible(plugin),
            canExecutePluginAction: (plugin: PluginRecord, options?: { notify?: boolean; allowCompatibilityOverride?: boolean }) => dependencies.dataController.canExecutePluginAction(plugin, options),
            setCompatibilityOverride: (plugin: PluginRecord, override: boolean, event?: Event): void => {
                trackPluginActionTask('setCompatibilityOverride', dependencies.stateActions.setCompatibilityOverride(plugin, override, event));
            },
            isPluginPermanentlyDisabled: (plugin: PluginRecord): boolean => dependencies.dataController.isPluginPermanentlyDisabled(plugin),
            notifyPluginIncompatible: (plugin: PluginRecord): void => dependencies.compatibilityController.notifyPluginIncompatible(plugin),
            isCircuitBreakerActive: (plugin: PluginRecord): boolean => dependencies.dataController.isCircuitBreakerActive(plugin),
            getPluginStatus: (plugin: PluginRecord): string => dependencies.dataController.getPluginStatus(plugin),
            resolvePluginRecord: (plugin: PluginRecord): PluginRecord | null => dependencies.dataController.resolvePluginRecord(plugin),
            getProviderCount: (plugin: PluginRecord): number => dependencies.dataController.getProviderCount(plugin)
        },
        lifecycle: {
            resetCircuitBreaker: (plugin: PluginRecord, event?: Event): void => {
                trackPluginActionTask('resetCircuitBreaker', dependencies.stateActions.resetCircuitBreaker(plugin, event));
            },
            togglePluginEnabled: (plugin: PluginRecord, event?: Event): void => {
                trackPluginActionTask('togglePluginEnabled', dependencies.stateActions.togglePluginEnabled(plugin, event));
            },
            stopPlugin: (plugin: PluginRecord): void => {
                trackPluginActionTask('stopPlugin', dependencies.stateActions.stopPlugin(plugin));
            }
        },
        navigation: {
            openInstallBackendModal: (plugin: PluginRecord): void => dependencies.openInstallBackendModal(plugin),
            openDownloadModelModal: (plugin: PluginRecord): void => dependencies.operationsController.openDownloadModelModal(plugin),
            openAddProviderModal: (plugin: PluginRecord): void => dependencies.operationsController.openAddProviderModal(plugin),
            openCloneModal: (plugin: PluginRecord): void => dependencies.openCloneModal(plugin),
            openManageBackendModal: (plugin: PluginRecord): void => dependencies.openManageBackendModal(plugin),
            navigateToModels: (action: string, plugin: PluginRecord): boolean => dependencies.navigateToModels(action, plugin),
            openPluginInfoModal: (plugin: PluginRecord): void => dependencies.openPluginInfoModal(plugin)
        }
    };
};

export { createPluginsActionHost };
export type { CreatePluginsActionHostDependencies };
