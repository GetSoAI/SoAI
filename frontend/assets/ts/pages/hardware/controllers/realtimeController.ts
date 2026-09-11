/* SoAI - Hardware page realtime controller [frontend/assets/ts/pages/hardware/controllers/realtimeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { HARDWARE, METRICS } from '@core/realtime/streammanager/resources/ids.ts';
import { isGpuSlotsBuilderResult } from '@core/realtime/streammanager/resources/gpuSlotsResource.ts';
import { isGpuCapabilitiesResource } from '@core/realtime/streammanager/resources/gpuCapabilitiesResource.ts';
import { decodeHardwareSnapshotResource, isHardwareProcessesResource } from '@core/realtime/streammanager/resources/resourceDecoders.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import type { DisposableResource } from '@core/resourcetracker/types.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { HistoryChartControlsManager } from '@features/charts/public.ts';
import { HistoryStateManager } from '@features/hardware/public.ts';
import type { ChartDataTransformsContract, ChartOhlcContract, ResourcesInterface } from '@pages/hardware/contracts/contracts.ts';
import type { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import type { GpuControlManager } from '@pages/hardware/controllers/gpucontrol/GpuControlManager.ts';
import type { HardwareRealtimeControllerDependencies } from '@pages/hardware/controllers/realtime/contracts.ts';
import { runChartBootstrap } from '@pages/hardware/controllers/realtime/hardwareRealtimeBootstrapController.ts';
import { cleanupHistoryStream, handleHistoryUpdate, startHistoryStream, type HardwareHistoryRuntime, type HardwareHistoryStreamDependencies } from '@pages/hardware/controllers/realtime/effects.ts';
import { loadHardwareInitialRealtimeSnapshots } from '@pages/hardware/controllers/realtime/initialSnapshotsController.ts';
import { loadHardwareWebuiPermissions } from '@pages/hardware/controllers/realtime/permissionsController.ts';
import { createHardwareHistoryHostCache, runHistoryFetch, type HardwareHistoryFetchDependencies, type HardwareHistoryHostCache, type HardwareHistoryHostDependencies } from '@pages/hardware/controllers/realtime/service.ts';
import { createHardwareHistoryStreamState, type HardwareHistoryStreamState } from '@pages/hardware/controllers/realtime/state.ts';
import { handleDecodedHardwareSnapshotRenderEvent, handleHardwareProcessRenderEvent, handleHardwareSnapshotRenderEvent, type HardwareRealtimeRenderEventContext } from '@pages/hardware/controllers/realtime/hardwareRealtimeRenderController.ts';
import { handleMetricsUpdate } from '@pages/hardware/controllers/render/rendering.ts';
import type { HardwareRenderController } from '@pages/hardware/controllers/renderController.ts';
import { disposeRealtimeHandles, initializeHardwareRealtime, setupRealtimeSubscriptions, type HardwareRealtimeHost, type HardwareRealtimeStreams } from '@pages/hardware/realtime/hardwarePageRealtime.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { HistoryRequestParameters, ModuleLoggerFunctionValue } from '@pages/hardware/types.ts';
import type { MemorySwapPanelController } from '@pages/hardware/widgets/memoryswap/MemorySwapPanelController.ts';
import type { ProcessTableManager } from '@pages/hardware/widgets/processes/service.ts';

import { HardwareGpuResourceState, type HardwareGpuResource } from '@pages/hardware/controllers/realtime/gpuResourceState.ts';

class HardwareRealtimeController implements HardwareRealtimeHost {
    readonly gpuResourceState = new HardwareGpuResourceState();
    state: HardwarePageState;
    dataController: HardwareDataController;
    renderController: HardwareRenderController;
    historyStateManager: HistoryStateManager;
    historyControlsManager: HistoryChartControlsManager;
    chartDataTransforms: ChartDataTransformsContract;
    chartOhlc: ChartOhlcContract;
    logger: ModuleLoggerFunctionValue;
    runWithBoundary: <T>(boundaryKey: string, functionValue: () => Promise<T>) => Promise<T>;
    handleError: (error: Error, message: string, options?: { notify?: boolean }) => void;
    getStreamManager: HardwareRealtimeControllerDependencies['getStreamManager'];
    peekStreamManager: HardwareRealtimeControllerDependencies['peekStreamManager'];
    ensureDataSubscriptions: (options?: { signal?: AbortSignal }) => Promise<void>;
    subscribeToResourceState: (resource: string, listener: (snapshot: ResourceReconciliationSnapshot) => void) => (() => void) | null;
    trackDisposable: (resource: DisposableResource, onDispose?: () => void) => void;
    resolveHasProcessPanel: () => boolean;
    resources: ResourcesInterface | null;
    gpuController: GpuControlManager;
    processController: ProcessTableManager;
    memorySwapController: MemorySwapPanelController;

    realtimeStreamActive: boolean = false;
    realtimeSubscriptionHandles: Set<() => void> = new Set();
    #chartBootstrapPromise: Promise<void> | null = null;
    #chartBootstrapSequence = 0;
    #realtimeReadyPromise: Promise<void> | null = null;
    #permissionsPromise: Promise<void> | null = null;

    historyStreamState: HardwareHistoryStreamState;
    historyHostCache: HardwareHistoryHostCache;
    historyHostDependencies: HardwareHistoryHostDependencies;
    historyStreamDependencies: HardwareHistoryStreamDependencies;
    historyRuntime: HardwareHistoryRuntime;
    historyFetchDependencies: HardwareHistoryFetchDependencies;
    renderEventContext: HardwareRealtimeRenderEventContext;

    constructor(dependencies: HardwareRealtimeControllerDependencies) {
        this.state = dependencies.state;
        this.dataController = dependencies.dataController;
        this.renderController = dependencies.renderController;
        this.historyStateManager = dependencies.historyStateManager;
        this.historyControlsManager = dependencies.historyControlsManager;
        this.chartDataTransforms = dependencies.chartDataTransforms;
        this.chartOhlc = dependencies.chartOhlc;
        this.logger = dependencies.logger;
        this.runWithBoundary = dependencies.runWithBoundary;
        this.handleError = dependencies.handleError;
        this.getStreamManager = dependencies.getStreamManager;
        this.peekStreamManager = dependencies.peekStreamManager;
        this.ensureDataSubscriptions = dependencies.ensureDataSubscriptions;
        this.subscribeToResourceState = dependencies.subscribeToResourceState;
        this.trackDisposable = dependencies.trackDisposable;
        this.resolveHasProcessPanel = dependencies.hasProcessPanel;
        this.resources = dependencies.resources;
        this.gpuController = dependencies.gpuController;
        this.gpuController.setResourceFreshness(this.gpuResourceState);
        this.processController = dependencies.processController;
        this.memorySwapController = dependencies.memorySwapController;
        this.historyStreamState = createHardwareHistoryStreamState();
        this.historyHostCache = createHardwareHistoryHostCache();
        this.historyFetchDependencies = {
            logger: this.logger
        };
        this.historyHostDependencies = {
            state: this.state,
            dataController: this.dataController,
            renderController: this.renderController,
            chartDataTransforms: this.chartDataTransforms,
            chartOhlc: this.chartOhlc,
            historyControlsManager: this.historyControlsManager,
            getHistoryRequestToken: () => this.historyStreamState.historyRequestToken,
            runHistoryFetch: (parameters, onResolve) => runHistoryFetch(this.historyFetchDependencies, this.historyStreamState, parameters, onResolve)
        };
        this.historyStreamDependencies = {
            state: this.state,
            dataController: this.dataController,
            renderController: this.renderController,
            historyStateManager: this.historyStateManager,
            logger: this.logger,
            runWithBoundary: this.runWithBoundary,
            handleError: this.handleError,
            prepareRealtimeResources: (options: { signal?: AbortSignal | undefined }) => this.#prepareRealtimeResources(options),
            peekStreamManager: this.peekStreamManager,
            historyHostDependencies: this.historyHostDependencies
        };
        this.historyRuntime = {
            historyState: this.historyStreamState,
            historyHostCache: this.historyHostCache
        };
        this.renderEventContext = {
            dataController: this.dataController,
            renderController: this.renderController,
            processController: this.processController,
            memorySwapController: this.memorySwapController,
            historyStreamState: this.historyStreamState,
            scheduleChartBootstrap: (scheduleOptions) => this.#scheduleChartBootstrap(scheduleOptions),
            handleChartBootstrapError: (error) => dependencies.handleError(error, 'Failed to bootstrap hardware charts'),
            handleHistoryUpdate: (data) => handleHistoryUpdate(this.historyStreamDependencies, this.historyRuntime, data)
        };
    }

    resolveStreamManager(options: { signal?: AbortSignal | undefined } = {}): Promise<StreamRuntimeOwners> {
        return this.getStreamManager({
            ensureReady: false,
            allowDiscovery: true,
            signal: options.signal ?? undefined
        });
    }

    hasGrantedAction(action: string): boolean {
        const actions = this.state.webuiPermissions?.actions ?? [];
        return actions.includes(action);
    }

    hasProcessPanel(): boolean {
        return this.resolveHasProcessPanel();
    }

    async ensureWebuiPermissionsLoaded(): Promise<void> {
        if (this.state.webuiPermissions) {
            return;
        }
        if (this.#permissionsPromise) {
            return this.#permissionsPromise;
        }
        const promise = loadHardwareWebuiPermissions({
            state: this.state,
            logger: this.logger,
            applyPermissionGates: () => this.renderController.applyPermissionGates()
        });
        this.#permissionsPromise = promise.finally(() => {
            if (this.#permissionsPromise === promise) {
                this.#permissionsPromise = null;
            }
        });
        return this.#permissionsPromise;
    }
    async prepareRealtimeResources(options: { signal?: AbortSignal | undefined } = {}): Promise<void> {
        await this.#prepareRealtimeResources(options);
    }

    async #prepareRealtimeResources(options: { signal?: AbortSignal | undefined } = {}): Promise<void> {
        if (this.#realtimeReadyPromise) return this.#realtimeReadyPromise;
        const streams: HardwareRealtimeStreams = {
            hardwareSnapshotStream: HARDWARE,
            systemMetricsStream: METRICS
        };
        const promise = (async (): Promise<void> => {
            await this.ensureWebuiPermissionsLoaded();
            await this.renderController.ensureChartModules();
            throwIfAborted(options.signal);
            await initializeHardwareRealtime(this, streams, this.logger, options.signal);
            throwIfAborted(options.signal);
            await loadHardwareInitialRealtimeSnapshots(this, options.signal);
            throwIfAborted(options.signal);
            if (this.state.lastSnapshot && !this.renderController.renderCache.widgetManagerInitialized) {
                handleDecodedHardwareSnapshotRenderEvent(this.renderEventContext, this.state.lastSnapshot, { scheduleChartBootstrap: false });
                await this.renderController.refreshChartControls();
                await this.renderController.waitForInitialWidgets();
            } else if (!this.state.lastSnapshot) {
                const rawSnapshot = await requestWebSocketSnapshotRecord(HARDWARE);
                this.handleSnapshot(decodeHardwareSnapshotResource(rawSnapshot), { scheduleChartBootstrap: false });
                await this.renderController.refreshChartControls();
                await this.renderController.waitForInitialWidgets();
            }
        })();
        this.#realtimeReadyPromise = promise.catch((error) => {
            this.#realtimeReadyPromise = null;
            throw ensureError(error);
        });
        return this.#realtimeReadyPromise;
    }
    scheduleChartBootstrap({ force = false, resetView = true, signal = null }: { force?: boolean; resetView?: boolean; signal?: AbortSignal | null } = {}): Promise<void> {
        return this.#scheduleChartBootstrap({ force, resetView, signal });
    }

    #scheduleChartBootstrap({ force = false, resetView = true, signal = null }: { force?: boolean; resetView?: boolean; signal?: AbortSignal | null } = {}): Promise<void> {
        if (this.#chartBootstrapPromise && !force) return this.#chartBootstrapPromise;
        if (force) {
            cleanupHistoryStream(this.historyStreamDependencies, this.historyRuntime);
        }
        this.#chartBootstrapSequence += 1;
        const bootstrapSequence = this.#chartBootstrapSequence;
        const bootstrapPromise = runChartBootstrap({
            state: this.state,
            renderController: this.renderController,
            historyStreamDependencies: this.historyStreamDependencies,
            historyRuntime: this.historyRuntime,
            signal: signal ?? null,
            resetView,
            sequence: bootstrapSequence,
            getCurrentSequence: () => this.#chartBootstrapSequence,
            prepareRealtimeResources: (options) => this.prepareRealtimeResources(options)
        });
        const trackedPromise = bootstrapPromise.finally(() => {
            if (this.#chartBootstrapPromise === trackedPromise) {
                this.#chartBootstrapPromise = null;
            }
        });
        this.#chartBootstrapPromise = trackedPromise;
        return this.#chartBootstrapPromise;
    }
    setupRealtimeSubscriptions(): void {
        setupRealtimeSubscriptions(this, {
            hardwareSnapshotStream: HARDWARE,
            systemMetricsStream: METRICS
        });
    }
    cleanupAllStreams(): void {
        this.gpuResourceState.invalidate();
        this.processController.reset();
        this.memorySwapController.resetProcessData();
        cleanupHistoryStream(this.historyStreamDependencies, this.historyRuntime);
        disposeRealtimeHandles(this);
        this.historyStreamState.historyFetchRequestToken = null;
    }

    async startHistoryStream({ resetView = false, signal = null }: { resetView?: boolean; signal?: AbortSignal | null | undefined } = {}): Promise<void> {
        return startHistoryStream(this.historyStreamDependencies, this.historyRuntime, { resetView, signal });
    }

    handleHistoryUpdate(data: import('@pages/hardware/types.ts').HardwarePageSnapshot): void {
        handleHistoryUpdate(this.historyStreamDependencies, this.historyRuntime, data);
    }

    processMetricsUpdate(value: JsonValue | null): void {
        const metrics = this.dataController.setMetrics(value);
        handleMetricsUpdate(this.renderController.actionsContext, metrics);
    }

    handleSnapshot(value: JsonValue | null, options: { scheduleChartBootstrap?: boolean } = {}): void {
        handleHardwareSnapshotRenderEvent(this.renderEventContext, value, options);
    }

    handleGpuCapabilities(value: JsonValue | null): void {
        if (!isGpuCapabilitiesResource(value)) throw new TypeError('hardware.gpu.capabilities stream must contain decoded capabilities');
        if (!this.hasGrantedAction('HW_GPU_TUNING')) return;
        this.gpuResourceState.acceptCapabilities(value);
        this.gpuController.setResourceFreshness(this.gpuResourceState);
        if (value.success) this.gpuController.setCapabilities(value);
    }

    handleSavedGpuSettings(value: JsonValue | null): void {
        if (!isGpuSlotsBuilderResult(value)) throw new TypeError('hardware.gpu.slots stream must contain decoded slot state');
        if (!this.hasGrantedAction('HW_GPU_TUNING')) return;
        this.gpuResourceState.acceptSlots(value);
        this.gpuController.setResourceFreshness(this.gpuResourceState);
        if (value.error === null) this.gpuController.setSavedSettings(value);
    }

    gpuResourceAvailable(resource: HardwareGpuResource): boolean {
        return this.gpuResourceState.usable(resource);
    }

    gpuResourceGeneration(resource: HardwareGpuResource): number {
        return this.gpuResourceState[resource].generation;
    }

    handleGpuResourceUnavailable(resource: HardwareGpuResource, error: Error): void {
        this.gpuResourceState.unavailable(resource);
        this.gpuController.setResourceFreshness(this.gpuResourceState);
        this.logger('debug', `GPU ${resource} resource unavailable`, error);
    }

    handleGpuResourceStale(resource: HardwareGpuResource, error: Error): void {
        this.gpuResourceState.stale(resource);
        this.gpuController.setResourceFreshness(this.gpuResourceState);
        this.logger('debug', `GPU ${resource} resource is recovering`, error);
    }

    handleSoAIBenchRunsUpdate(value: JsonValue | null): void {
        if (!isJsonObject(value)) throw new TypeError('SoAIBench runs payload must be an object');
        this.state.soaibenchRuns = value;
        this.gpuController.setSoAIBenchRuns(value);
    }

    handleProcessResourceUpdate(value: JsonValue | null): void {
        if (!isHardwareProcessesResource(value)) throw new TypeError('hardware.processes stream must contain decoded process records');
        handleHardwareProcessRenderEvent(this.renderEventContext, value);
    }

    runHistoryFetch(parameters: HistoryRequestParameters, onResolve: (result: JsonValue | null) => Promise<void>): Promise<void> {
        return runHistoryFetch(this.historyFetchDependencies, this.historyStreamState, parameters, onResolve);
    }

    resetBootstrapState(): void {
        this.#chartBootstrapSequence += 1;
        this.#chartBootstrapPromise = null;
        this.#realtimeReadyPromise = null;
    }
}

export { HardwareRealtimeController };
