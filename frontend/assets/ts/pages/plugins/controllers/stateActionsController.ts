/* SoAI - Plugins page state actions controller [frontend/assets/ts/pages/plugins/controllers/stateActionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { resetPluginCircuitBreaker, setPluginCompatibilityOverride, stopPluginProcess, togglePluginEnabledState, type PluginsStateActionHost } from '@pages/plugins/state/pluginsStateActions.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface PluginsStateActionsControllerDependencies extends PageFeedbackOwnerHost {
    activeToggles: Set<string>;
    pendingToggleTargets: Map<string, boolean>;
    api: PluginsStateActionHost['api'];
    catalogStore: PluginsStateActionHost['catalogStore'];
    runWithBoundary<T>(scope: string, task: () => Promise<T>): Promise<T>;
    runPageTask<Result>(taskKey: string, task: () => Promise<Result>, options: { displayName: string; rethrow?: boolean }): Promise<Result | null>;
    runPluginTaskAction(taskKey: string, endpoint: string, options: { pluginName: string; displayName: string; onAccepted?: (taskId: string) => void }): Promise<Record<string, JsonValue> | null>;
    commitCatalogPlugin(plugin: ResourceIncomingValue): PluginRecord | null;
    rerenderPlugin(pluginName: string): void;
    isHardwareIncompatible(plugin: PluginRecord): boolean;
    canExecutePluginAction(plugin: PluginRecord, options?: { allowCompatibilityOverride?: boolean }): boolean;
    getPluginStatus(plugin: PluginRecord): string;
    isPluginPermanentlyDisabled(plugin: PluginRecord): boolean;
    notifyPluginIncompatible(plugin: PluginRecord): void;
    isPluginStoppable(plugin: PluginRecord): boolean;
}

class PluginsStateActionsController {
    readonly #dependencies: PluginsStateActionsControllerDependencies;
    readonly #stateActionHost: PluginsStateActionHost;

    constructor(dependencies: PluginsStateActionsControllerDependencies) {
        this.#dependencies = dependencies;
        this.#stateActionHost = this.#createStateActionHost();
    }

    #createStateActionHost(): PluginsStateActionHost {
        return {
            activeToggles: this.#dependencies.activeToggles,
            pendingToggleTargets: this.#dependencies.pendingToggleTargets,
            api: this.#dependencies.api,
            catalogStore: this.#dependencies.catalogStore,
            runWithBoundary: (scope, task) => this.#dependencies.runWithBoundary(scope, task),
            runPageTask: (taskKey, task, options) => this.#dependencies.runPageTask(taskKey, task, options),
            runPluginTaskAction: (taskKey, endpoint, options) => this.#dependencies.runPluginTaskAction(taskKey, endpoint, options),
            commitCatalogPlugin: (plugin: ResourceIncomingValue) => this.#dependencies.commitCatalogPlugin(plugin),
            rerenderPlugin: (pluginName: string): void => this.#dependencies.rerenderPlugin(pluginName),
            feedback: this.#dependencies.feedback,
            isHardwareIncompatible: (plugin: PluginRecord): boolean => this.#dependencies.isHardwareIncompatible(plugin),
            canExecutePluginAction: (plugin: PluginRecord, options?: { allowCompatibilityOverride?: boolean }) => this.#dependencies.canExecutePluginAction(plugin, options),
            getPluginStatus: (plugin: PluginRecord): string => this.#dependencies.getPluginStatus(plugin),
            isPluginPermanentlyDisabled: (plugin: PluginRecord): boolean => this.#dependencies.isPluginPermanentlyDisabled(plugin),
            notifyPluginIncompatible: (plugin: PluginRecord): void => this.#dependencies.notifyPluginIncompatible(plugin),
            isPluginStoppable: (plugin: PluginRecord): boolean => this.#dependencies.isPluginStoppable(plugin)
        };
    }

    async resetCircuitBreaker(plugin: PluginRecord, event?: Event): Promise<void> {
        return resetPluginCircuitBreaker(this.#stateActionHost, plugin, event);
    }

    async togglePluginEnabled(plugin: PluginRecord, event?: Event): Promise<void> {
        return togglePluginEnabledState(this.#stateActionHost, plugin, event);
    }

    async setCompatibilityOverride(plugin: PluginRecord, override: boolean, event?: Event): Promise<void> {
        return setPluginCompatibilityOverride(this.#stateActionHost, plugin, override, event);
    }

    async stopPlugin(plugin: PluginRecord): Promise<void> {
        await stopPluginProcess(this.#stateActionHost, plugin);
    }
}

export { PluginsStateActionsController };
export type { PluginsStateActionsControllerDependencies };
