/* SoAI - Hardware page realtime contracts [frontend/assets/ts/pages/hardware/controllers/realtime/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DisposableResource } from '@core/resourcetracker/types.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { GetStreamManagerOptions, PeekStreamManagerOptions } from '@core/lifecyclemodel/types.ts';
import type { HistoryChartControlsManager } from '@features/charts/public.ts';
import type { HistoryStateManager } from '@features/hardware/public.ts';
import type { ChartDataTransformsContract, ChartOhlcContract, ResourcesInterface } from '@pages/hardware/contracts/contracts.ts';
import type { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import type { GpuControlManager } from '@pages/hardware/controllers/gpucontrol/GpuControlManager.ts';
import type { HardwareRenderController } from '@pages/hardware/controllers/renderController.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { ModuleLoggerFunctionValue } from '@pages/hardware/types.ts';
import type { MemorySwapPanelController } from '@pages/hardware/widgets/memoryswap/MemorySwapPanelController.ts';
import type { ProcessTableManager } from '@pages/hardware/widgets/processes/service.ts';

type HardwareRealtimeControllerDependencies = {
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
    getStreamManager: (options: GetStreamManagerOptions) => Promise<StreamRuntimeOwners>;
    peekStreamManager: (options: PeekStreamManagerOptions) => StreamRuntimeOwners | null;
    ensureDataSubscriptions: (options?: { signal?: AbortSignal }) => Promise<void>;
    subscribeToData: (resource: string, handler: (value: JsonValue) => void) => (() => void) | null;
    trackDisposable: (resource: DisposableResource, onDispose?: () => void) => void;
    hasProcessPanel: () => boolean;
    resources: ResourcesInterface | null;
    gpuController: GpuControlManager;
    processController: ProcessTableManager;
    memorySwapController: MemorySwapPanelController;
};

export type { HardwareRealtimeControllerDependencies };
