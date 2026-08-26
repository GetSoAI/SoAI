/* SoAI - Dashboard page boundary contracts [frontend/assets/ts/pages/dashboard/contracts/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { RequestDistributionChartSizeWatcher } from '@core/models/requestDistributionChartSizing.ts';
import type { MovableLayoutEditController } from '@core/routing/pages/movablesections/layoutEditController.ts';
import type { MovableSectionLayout } from '@core/routing/pages/movablesections/service.ts';
import type { MovableSectionLayoutHost, MovableSectionLayoutStorage } from '@core/routing/pages/movablesections/types.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import type { DashboardActionId } from '@pages/dashboard/actions.ts';
import type { StatusManagerContract } from '@pages/dashboard/contracts/constants.ts';
import type { DashboardEditionContribution, DashboardHost, DashboardProductSectionController, DashboardTimerControl } from '@core/edition/dashboardContribution.ts';
import type { DashboardBlueprint, DashboardBlueprintId } from '@pages/dashboard/controllers/dashboardBlueprints.ts';
import type { DashboardClockController } from '@pages/dashboard/controllers/dashboardClockWidget.ts';
import type { DashboardThroughputController } from '@pages/dashboard/controllers/dashboardThroughputWidget.ts';
import type { createDashboardCollectionsRenderers } from '@pages/dashboard/controllers/dashboardCollectionsSection.ts';
import type { DashboardHardwareSectionsController } from '@pages/dashboard/controllers/dashboardHardwareSectionsController.ts';
import type { DashboardImageCardController, DashboardImageCardStorage } from '@pages/dashboard/controllers/dashboardImageCardController.ts';
import type { DashboardMemoController, DashboardMemoStorage } from '@pages/dashboard/controllers/dashboardMemoController.ts';
import type { DashboardLiveDataContext, DashboardLiveDataKey } from '@pages/dashboard/controllers/dashboardLiveData.ts';
import type { DashboardSectionRenderQueue } from '@pages/dashboard/controllers/effects.ts';
import type { DashboardLogs } from '@pages/dashboard/widgets/logs/index.ts';
import type { DashboardLogStream } from '@pages/dashboard/widgets/logs/types.ts';

type DashboardRuntimeHostDependencies = DashboardHost;

type DashboardRuntimeSectionLayoutHostDependencies = MovableSectionLayoutHost;

type DashboardRuntimeSectionLayoutStorageDependencies = MovableSectionLayoutStorage;

interface DashboardRuntimeLogsHostDependencies {
    storageGet: (key: string, defaultValue?: JsonValue | null) => JsonValue | null;
    storageSet: (key: string, value: JsonValue | null) => void;
    replaceElementContent: (target: Element, content: string | TrustedHtml | DocumentFragment | HTMLElement, options?: { escape?: boolean }) => void;
    flushDOMUpdates: () => void;
    optionalHTMLElement: (selector: string, context?: Element | null) => HTMLElement | null;
    updateProperty: (element: Element | null, property: string, value: DomPropertyValue) => void;
    updateStyle: (element: Element | null, property: string, value: string) => void;
    updateHTML: (element: Element | null, html: string | TrustedHtml, options?: { escape?: boolean }) => void;
    ensureLogStreamReady: () => Promise<DashboardLogStream>;
    logError: (message: string, detail?: JsonValue | Error | null) => void;
    isDestroyed: () => boolean;
    showNotification: (message: string, type: NotificationType) => void;
}

interface DashboardRuntimeDependencies {
    host: DashboardRuntimeHostDependencies;
    sectionLayoutHost: DashboardRuntimeSectionLayoutHostDependencies;
    sectionLayoutStorage: DashboardRuntimeSectionLayoutStorageDependencies;
    imageCardStorage: DashboardImageCardStorage;
    memoStorage: DashboardMemoStorage;
    logsHost: DashboardRuntimeLogsHostDependencies;
    timers: DashboardTimerControl;
    on: (target: EventTarget, event: string, handler: EventListener, options?: AddEventListenerOptions) => () => void;
    navigate: (route: string) => void;
    getBlueprints: () => Map<DashboardBlueprintId, DashboardBlueprint> | null;
    getCurrentStatus: () => StatusManagerContract | null;
    getDashboardLocked: () => boolean;
    getClockSecondsEnabled: () => boolean;
    isAdmin: () => boolean;
    isDestroyed: () => boolean;
    logDebug: (message: string, detail?: JsonValue | Error | null) => void;
    genericStorage: DashboardGenericStorage;
    onLogsAction: (actionId: DashboardActionId, target: HTMLElement) => void;
    imageActions: DashboardImageActionPort;
    edition: DashboardEditionContribution | null;
}

interface DashboardGenericStorage {
    get: (key: string, defaultValue?: JsonValue | null) => JsonValue | null;
    set: (key: string, value: JsonValue | null) => void;
}

interface DashboardImageActionPort {
    onUploadOpen: () => void;
    onDelete: () => void;
    onToggleFit: () => void;
}

interface DashboardRuntime {
    readonly host: DashboardHost;
    readonly sectionRenderQueue: DashboardSectionRenderQueue;
    readonly collectionsRenderers: ReturnType<typeof createDashboardCollectionsRenderers>;
    readonly renderStatusSection: () => void;
    readonly renderRequestsSection: () => void;
    readonly requestDistributionChartSizeWatcher: RequestDistributionChartSizeWatcher;
    readonly hardwareSections: DashboardHardwareSectionsController;
    readonly imageCard: DashboardImageCardController;
    readonly clock: DashboardClockController;
    readonly throughput: DashboardThroughputController;
    readonly layoutEdit: MovableLayoutEditController<DashboardBlueprintId>;
    readonly memo: DashboardMemoController;
    readonly layout: MovableSectionLayout<DashboardBlueprintId>;
    readonly logs: DashboardLogs;
    readonly actionHandlers: Readonly<Record<DashboardActionId, (actionElement: HTMLElement) => void>>;
    readonly liveDataContext: DashboardLiveDataContext;
    readonly productSection: DashboardProductSectionController | null;
    hasDashboardLiveData: (key: DashboardLiveDataKey) => boolean;
    createBlueprints(): Map<DashboardBlueprintId, DashboardBlueprint>;
}

export type { DashboardGenericStorage, DashboardRuntime, DashboardRuntimeDependencies, DashboardRuntimeHostDependencies, DashboardRuntimeSectionLayoutHostDependencies, DashboardRuntimeSectionLayoutStorageDependencies, DashboardRuntimeLogsHostDependencies, DashboardHost };
export type { DashboardActionId };
export type { DashboardImageCardStorage, DashboardMemoStorage, DashboardLiveDataContext, DashboardLiveDataKey, DashboardSectionRenderQueue, StatusManagerContract };
