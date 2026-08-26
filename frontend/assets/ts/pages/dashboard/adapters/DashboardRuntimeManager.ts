/* SoAI - Dashboard page runtime manager [frontend/assets/ts/pages/dashboard/adapters/DashboardRuntimeManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { hasWebuiAction } from '@core/access/webuiPermissions.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getLogValidation } from '@core/logvalidation/public.ts';
import { RequestDistributionChartSizeWatcher } from '@core/models/requestDistributionChartSizing.ts';
import { DASHBOARD_REQUEST_DISTRIBUTION_SOURCE_STORAGE_KEY, createRequestDistributionViewState } from '@core/models/requestDistributionRendering.ts';
import { MovableLayoutEditController } from '@core/routing/pages/movablesections/layoutEditController.ts';
import { MovableSectionLayout } from '@core/routing/pages/movablesections/service.ts';
import type { ElementOptions } from '@core/dom/dom.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';
import type { HardwareData, HardwareSnapshot } from '@features/hardware/public.ts';
import type { DashboardHost, DashboardRuntime, DashboardRuntimeDependencies, StatusManagerContract } from '@pages/dashboard/contracts/contracts.ts';
import { createDashboardBlueprints, type DashboardBlueprint, type DashboardBlueprintId } from '@pages/dashboard/controllers/dashboardBlueprints.ts';
import { DashboardClockController } from '@pages/dashboard/controllers/dashboardClockWidget.ts';
import { createDashboardCollectionsRenderers } from '@pages/dashboard/controllers/dashboardCollectionsSection.ts';
import { DashboardHardwareSectionsController } from '@pages/dashboard/controllers/dashboardHardwareSectionsController.ts';
import { DashboardImageCardController } from '@pages/dashboard/controllers/dashboardImageCardController.ts';
import { DashboardMemoController } from '@pages/dashboard/controllers/dashboardMemoController.ts';
import { createDashboardQuickActionsSectionRenderer } from '@pages/dashboard/controllers/dashboardQuickActionsWidget.ts';
import { DashboardThroughputController } from '@pages/dashboard/controllers/dashboardThroughputWidget.ts';
import type { DashboardLiveDataContext, DashboardLiveDataKey } from '@pages/dashboard/controllers/dashboardLiveData.ts';
import { createDashboardRequestsSectionRenderer, syncDashboardRequestDistributionSourceToggle } from '@pages/dashboard/controllers/dashboardRequestsSection.ts';
import { createDashboardStatusSectionRenderer } from '@pages/dashboard/controllers/dashboardStatusSection.ts';
import { createDashboardSectionRenderQueue } from '@pages/dashboard/controllers/effects.ts';
import { createDashboardActionHandlers } from '@pages/dashboard/controllers/events.ts';
import { createDashboardMovableLayoutConfig } from '@pages/dashboard/rendering/layout/service.ts';
import { renderDashboardSection, resolveDashboardStatusManager } from '@pages/dashboard/services/service.ts';
import { createInitialDashboardState } from '@pages/dashboard/state/dashboardStateModel.ts';
import { DashboardLogs } from '@pages/dashboard/widgets/logs/index.ts';

const createDashboardHost = (dependencies: DashboardRuntimeDependencies['host']): DashboardHost => {
    return {
        notify: (message: string, level: 'error' | 'success' | 'info' | 'warning'): void => dependencies.notify(message, level),
        createElement: (tag: string, attrs?: ElementOptions, text?: string): Element => dependencies.createElement(tag, attrs, text),
        replaceElementContent: (target: Element, content: string | TrustedHtml | DocumentFragment | HTMLElement, options?: { escape?: boolean }): void => dependencies.replaceElementContent(target, content, options),
        flushDOMUpdates: (): void => dependencies.flushDOMUpdates(),
        optionalUI: (selector: string, context?: Element | null): Element | null => dependencies.optionalUI(selector, context ?? undefined),
        requireUI: (selector: string, context?: Element | null): Element => dependencies.requireUI(selector, context ?? undefined),
        optionalHTMLElement: (selector: string, context?: Element | null): HTMLElement | null => dependencies.optionalHTMLElement(selector, context ?? undefined),
        requireHTMLElement: (selector: string, context?: Element | null): HTMLElement => dependencies.requireHTMLElement(selector, context ?? undefined),
        sanitizeText: (value: string): string => dependencies.sanitizeText(value),
        getStyleProp: (name: string): string | null => dependencies.getStyleProp(name)
    };
};

const createDashboardRuntime = (dependencies: DashboardRuntimeDependencies): DashboardRuntime => {
    const host = createDashboardHost(dependencies.host);
    const liveDataContext: DashboardLiveDataContext = {
        state: createInitialDashboardState(),
        rawHardwareSnapshot: null,
        dataReceived: new Set<DashboardLiveDataKey>(),
        sectionDataFingerprints: new Map()
    };
    const sectionRenderQueue = createDashboardSectionRenderQueue({
        renderSection: async (sectionId): Promise<void> => await renderDashboardSection(dependencies.getBlueprints(), sectionId),
        isDestroyed: (): boolean => dependencies.isDestroyed()
    });
    const productSection =
        dependencies.edition?.createSection({
            host,
            isDestroyed: (): boolean => dependencies.isDestroyed()
        }) ?? null;
    const requestDistributionViewState = createRequestDistributionViewState({
        includeApiKeys: dependencies.isAdmin(),
        storageKey: DASHBOARD_REQUEST_DISTRIBUTION_SOURCE_STORAGE_KEY,
        storage: {
            get: (key, defaultValue): JsonValue => dependencies.genericStorage.get(key, defaultValue),
            set: (key, value): void => {
                dependencies.genericStorage.set(key, value ?? null);
            }
        }
    });
    const requestDistributionChartSizeWatcher = new RequestDistributionChartSizeWatcher();
    let apiKeyUsagePermissionRequest: Promise<boolean> | null = null;
    const requestApiKeyUsagePermission = (): Promise<boolean> => {
        apiKeyUsagePermissionRequest ??= dependencies.isAdmin() ? hasWebuiAction('OPENAI_API_ADMIN') : Promise.resolve(false);
        return apiKeyUsagePermissionRequest;
    };
    let apiKeyUsageSnapshot: JsonValue | null = null;
    let apiKeyUsageSnapshotLoaded = false;
    let apiKeyUsageSnapshotRequest: Promise<void> | null = null;
    const sectionHasData = (key: DashboardLiveDataKey): boolean => liveDataContext.dataReceived.has(key);
    const statusManager = (): StatusManagerContract | null => resolveDashboardStatusManager({ status: dependencies.getCurrentStatus() });
    const renderStatusSection = createDashboardStatusSectionRenderer({
        host,
        getMetrics: (): JsonValue => liveDataContext.state.metrics,
        getPlugins: (): readonly JsonValue[] => liveDataContext.state.plugins,
        getModels: (): readonly JsonValue[] => liveDataContext.state.models,
        getStatusManager: (): StatusManagerContract | null => statusManager()
    });
    const renderRequestsSection = (options: { transition?: boolean } = {}): void => {
        createDashboardRequestsSectionRenderer({
            host,
            chartSizeWatcher: requestDistributionChartSizeWatcher,
            getMetrics: (): JsonValue => liveDataContext.state.metrics,
            getApiKeyUsage: (): JsonValue | null => apiKeyUsageSnapshot,
            hasApiKeyUsage: (): boolean => apiKeyUsageSnapshotLoaded,
            hasMetrics: (): boolean => sectionHasData('metrics'),
            requestApiKeyUsage: (): void => {
                if (!dependencies.isAdmin() || dependencies.isDestroyed() || apiKeyUsageSnapshotRequest) {
                    return;
                }
                apiKeyUsageSnapshotRequest = requestApiKeyUsagePermission()
                    .then((allowed) => (allowed ? requestWebSocketSnapshotPayload('openai_api_keys.usage') : null))
                    .then((snapshot): void => {
                        if (dependencies.isDestroyed()) {
                            return;
                        }
                        apiKeyUsageSnapshot = snapshot;
                        apiKeyUsageSnapshotLoaded = true;
                        renderRequestsSection();
                    })
                    .catch((error): void => {
                        if (!dependencies.isDestroyed()) {
                            apiKeyUsageSnapshot = null;
                            apiKeyUsageSnapshotLoaded = true;
                            renderRequestsSection();
                        }
                        dependencies.logDebug('Dashboard API key usage snapshot failed', ensureError(error));
                    })
                    .finally((): void => {
                        apiKeyUsageSnapshotRequest = null;
                        apiKeyUsagePermissionRequest = null;
                    });
            },
            viewState: requestDistributionViewState
        })(options);
    };
    const collectionsRenderers = createDashboardCollectionsRenderers({
        host,
        getStatusManager: (): StatusManagerContract | null => statusManager(),
        isDestroyed: (): boolean => dependencies.isDestroyed()
    });
    const hardwareSections = new DashboardHardwareSectionsController({
        host,
        state: {
            hasHardware: (): boolean => sectionHasData('hardware'),
            getRawHardwareSnapshot: (): HardwareSnapshot | HardwareData | null => liveDataContext.rawHardwareSnapshot
        },
        isDestroyed: (): boolean => dependencies.isDestroyed()
    });
    const imageCard = new DashboardImageCardController({
        host,
        storage: dependencies.imageCardStorage,
        isDestroyed: (): boolean => dependencies.isDestroyed()
    });
    const memo = new DashboardMemoController({
        host,
        storage: dependencies.memoStorage,
        isDestroyed: (): boolean => dependencies.isDestroyed()
    });
    const clock = new DashboardClockController({
        host,
        timers: dependencies.timers,
        on: dependencies.on,
        getClockSecondsEnabled: (): boolean => dependencies.getClockSecondsEnabled(),
        isDestroyed: (): boolean => dependencies.isDestroyed()
    });
    const throughput = new DashboardThroughputController({
        host,
        timers: dependencies.timers,
        getMetrics: (): JsonValue => liveDataContext.state.metrics,
        isDestroyed: (): boolean => dependencies.isDestroyed()
    });
    const renderQuickActionsSection = createDashboardQuickActionsSectionRenderer({
        host,
        productActions: dependencies.edition?.quickActions ?? []
    });
    const layout = new MovableSectionLayout({
        host: dependencies.sectionLayoutHost,
        storage: dependencies.sectionLayoutStorage,
        config: createDashboardMovableLayoutConfig(dependencies.edition)
    });
    const layoutEdit = new MovableLayoutEditController({
        layout,
        contextId: 'dashboard.layout',
        saveUnitId: 'dashboard.layout',
        requestContextLabel: 'Dashboard layout save',
        isCustomizationDisabled: (): boolean => dependencies.getDashboardLocked()
    });
    const logs = new DashboardLogs({
        host: dependencies.logsHost,
        validator: getLogValidation()
    });
    const actionHandlers = createDashboardActionHandlers({
        onLogsAction: dependencies.onLogsAction,
        onImageUploadOpen: dependencies.imageActions.onUploadOpen,
        onImageDelete: dependencies.imageActions.onDelete,
        onImageToggleFit: dependencies.imageActions.onToggleFit,
        onMemoCancel: (): void => memo.cancelEditing(),
        onMemoEdit: (): void => memo.startEditing(),
        onMemoSave: (): void => {
            terminateHandledPromise(memo.requestSave());
        },
        onClockModeCycle: (): void => {
            clock.cycleMode();
        },
        onRequestDistributionSourceToggle: (): void => {
            requestDistributionViewState.toggleSource();
            syncDashboardRequestDistributionSourceToggle(host, requestDistributionViewState);
            renderRequestsSection({ transition: true });
        },
        onQuickActionNavigate: (pageId: string): void => {
            dependencies.navigate(pageId);
        }
    });
    const createBlueprints = (): Map<DashboardBlueprintId, DashboardBlueprint> => {
        return createDashboardBlueprints({
            includeProductCapabilities: productSection !== null,
            renderers: {
                renderStatusSection: () => renderStatusSection(),
                renderProductCapabilitiesSection: () => {
                    if (!productSection) {
                        throw new Error('Dashboard product capabilities renderer requires an edition contribution');
                    }
                    productSection.render();
                },
                renderPluginsSection: () => collectionsRenderers.renderPluginsSection(liveDataContext.state.plugins, (): boolean => sectionHasData('plugins')),
                renderModelsSection: () => collectionsRenderers.renderModelsSection(liveDataContext.state.models, (): boolean => sectionHasData('models')),
                renderHardwareWidgetsSection: () => hardwareSections.renderHardwareWidgetsSection(),
                renderNetworkInterfacesSection: () => hardwareSections.renderNetworkInterfacesSection(),
                renderStorageSection: () => hardwareSections.renderStorageSection(),
                renderImageCardSection: () => imageCard.renderSection(),
                renderMemoSection: () => memo.renderSection(),
                renderClockSection: () => clock.renderSection(),
                renderThroughputSection: () => throughput.renderSection(),
                renderQuickActionsSection: () => renderQuickActionsSection(),
                renderRequestsSection: () => renderRequestsSection(),
                renderLogs: () => logs.render(),
                getRequestDistributionSource: () => requestDistributionViewState.getSource(),
                getRequestDistributionNextSource: () => requestDistributionViewState.getNextSource(),
                buildImageCardControls: () => imageCard.buildControlsMarkup(),
                buildMemoControls: () => memo.buildControlsMarkup()
            }
        });
    };
    return {
        host,
        sectionRenderQueue,
        collectionsRenderers,
        renderStatusSection,
        renderRequestsSection,
        requestDistributionChartSizeWatcher,
        hardwareSections,
        imageCard,
        clock,
        throughput,
        layoutEdit,
        memo,
        layout,
        logs,
        actionHandlers,
        liveDataContext,
        productSection,
        hasDashboardLiveData: (key: DashboardLiveDataKey): boolean => sectionHasData(key),
        createBlueprints
    };
};

export { createDashboardRuntime };
export type { DashboardRuntime } from '@pages/dashboard/contracts/contracts.ts';
