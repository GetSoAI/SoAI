/* SoAI - Dashboard page services service [frontend/assets/ts/pages/dashboard/services/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { RequestDistributionChartSizeWatcher } from '@core/models/requestDistributionChartSizing.ts';
import { getMainStatusMonitor } from '@core/mainstatusmonitor/public.ts';
import { updateMainStateIndicatorUI } from '@features/indicators/public.ts';
import { DASHBOARD_REQUIRED_STREAMS, isStatusManagerContract, type StatusManagerContract } from '@pages/dashboard/contracts/constants.ts';
import type { DashboardBlueprint, DashboardBlueprintId } from '@pages/dashboard/controllers/dashboardBlueprints.ts';
import type { DashboardLiveDataKey, DashboardSectionId } from '@pages/dashboard/controllers/dashboardLiveData.ts';
import { handleDashboardLiveDataUpdate, setupDashboardMainStateMonitoring, setupDashboardSubscriptions, type DashboardSectionRenderQueue } from '@pages/dashboard/controllers/effects.ts';

interface DashboardStatusSource {
    status?: StatusManagerContract | null;
}

interface DashboardSubscriptionSetupDependencies {
    subscribeToData: (resource: string, handler: (payload: JsonValue) => void) => () => void;
    registerDashboardSubscription: (subscription: () => void) => void;
    handleLiveData: (type: DashboardLiveDataKey, payload: JsonValue) => void;
    getMainStateIndicator: () => Element | null;
}

interface DashboardSectionRenderDependencies {
    isDestroyed: () => boolean;
    blueprints: Map<DashboardBlueprintId, DashboardBlueprint> | null;
    queue: DashboardSectionRenderQueue;
}

const resolveDashboardStatusManager = (source: DashboardStatusSource | undefined): StatusManagerContract | null => {
    const status = source?.status;
    return isStatusManagerContract(status) ? status : null;
};

const createMainStateMonitorCleanup = (dependencies: { getMainStateIndicator: () => Element | null }): (() => void) => {
    return setupDashboardMainStateMonitoring({
        subscribeMainState: (callback: (state: string) => void): (() => void) => {
            return getMainStatusMonitor().subscribe((state: string): void => {
                callback(state);
            });
        },
        updateMainStateIndicator: (state: string): void => {
            const element = dependencies.getMainStateIndicator();
            if (element instanceof HTMLElement) {
                updateMainStateIndicatorUI(element, state);
            }
        }
    });
};

const runDashboardSubscriptions = (dependencies: DashboardSubscriptionSetupDependencies): (() => void) => {
    setupDashboardSubscriptions({
        subscriptions: DASHBOARD_REQUIRED_STREAMS,
        subscribeToData: dependencies.subscribeToData,
        registerDashboardSubscription: dependencies.registerDashboardSubscription,
        handleLiveData: (type: DashboardLiveDataKey, payload: JsonValue): void => {
            dependencies.handleLiveData(type, payload);
        }
    });
    return createMainStateMonitorCleanup({ getMainStateIndicator: dependencies.getMainStateIndicator });
};

const queueDashboardSectionRender = (dependencies: DashboardSectionRenderDependencies, sectionId: DashboardSectionId): void => {
    if (dependencies.isDestroyed() || !dependencies.blueprints) {
        return;
    }
    dependencies.queue.queueSectionRender(sectionId);
};

const renderDashboardSection = async (blueprints: Map<DashboardBlueprintId, DashboardBlueprint> | null, sectionId: DashboardSectionId): Promise<void> => {
    const blueprint = blueprints?.get(sectionId);
    if (!blueprint) {
        throw new Error(`Dashboard blueprint missing for section "${sectionId}"`);
    }
    await blueprint.render();
};

interface DashboardDestroyable {
    destroy: () => void;
}

interface DashboardWidgetRuntimeLifecycle {
    logs: DashboardDestroyable;
    hardwareSections: DashboardDestroyable;
    memo: DashboardDestroyable;
    clock: DashboardDestroyable;
    throughput: DashboardDestroyable;
    layoutEdit: DashboardDestroyable;
    layout: DashboardDestroyable;
    requestDistributionChartSizeWatcher: RequestDistributionChartSizeWatcher;
}

const destroyDashboardWidgetRuntime = (runtime: DashboardWidgetRuntimeLifecycle): void => {
    runtime.logs.destroy();
    runtime.hardwareSections.destroy();
    runtime.memo.destroy();
    runtime.clock.destroy();
    runtime.throughput.destroy();
    runtime.layoutEdit.destroy();
    runtime.layout.destroy();
    runtime.requestDistributionChartSizeWatcher.disconnect();
};

export { destroyDashboardWidgetRuntime, queueDashboardSectionRender, renderDashboardSection, resolveDashboardStatusManager, handleDashboardLiveDataUpdate, runDashboardSubscriptions };
