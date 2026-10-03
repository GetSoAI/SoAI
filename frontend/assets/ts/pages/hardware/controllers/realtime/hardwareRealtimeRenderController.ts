/* SoAI - Hardware page control layer realtime render controller [frontend/assets/ts/pages/hardware/controllers/realtime/hardwareRealtimeRenderController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { HardwareProcessesResource } from '@core/realtime/streammanager/resources/resourceValueContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import { applyChartDataLimits } from '@pages/hardware/controllers/render/effects.ts';
import type { HardwareRenderController } from '@pages/hardware/controllers/renderController.ts';
import type { MemorySwapPanelController } from '@pages/hardware/widgets/memoryswap/MemorySwapPanelController.ts';
import type { ProcessTableManager } from '@pages/hardware/widgets/processes/service.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';

type HardwareRealtimeRenderEventContext = {
    dataController: HardwareDataController;
    renderController: HardwareRenderController;
    processController: ProcessTableManager;
    memorySwapController: MemorySwapPanelController;
    scheduleChartBootstrap: (options: { force: boolean; resetView: boolean }) => Promise<void>;
    handleChartBootstrapError: (error: Error) => void;
    handleHistoryUpdate: (data: HardwarePageSnapshot) => void;
};

const handleHardwareSnapshotRenderEvent = (context: HardwareRealtimeRenderEventContext, value: JsonValue, options: { scheduleChartBootstrap?: boolean } = {}): void => {
    handleDecodedHardwareSnapshotRenderEvent(context, context.dataController.decodeSnapshot(value), options);
};

const handleDecodedHardwareSnapshotRenderEvent = (context: HardwareRealtimeRenderEventContext, decodedSnapshot: HardwarePageSnapshot, options: { scheduleChartBootstrap?: boolean } = {}): void => {
    const hadCapabilities = Boolean(context.dataController.state.hardwareCapabilities);
    const snapshot = context.dataController.setSnapshot(decodedSnapshot);
    if (!hadCapabilities) {
        const capabilitiesRaw = snapshot.capabilities;
        const applied = context.dataController.setHardwareCapabilities(capabilitiesRaw);
        if (!applied) {
            throw new TypeError('hardware.snapshot must include capabilities');
        }
        applyChartDataLimits(context.renderController.chartContext);
    }
    context.memorySwapController.handleSnapshot(snapshot);
    const selectionChanged = context.renderController.handleSnapshot(snapshot);
    if (selectionChanged && options.scheduleChartBootstrap !== false) {
        void context.scheduleChartBootstrap({ force: true, resetView: true }).catch((error) => {
            context.handleChartBootstrapError(ensureError(error));
        });
    }
    context.handleHistoryUpdate(snapshot);
};

const handleHardwareProcessRenderEvent = (context: HardwareRealtimeRenderEventContext, value: HardwareProcessesResource): void => {
    context.memorySwapController.handleProcessResourceUpdate(value);
    context.processController.handleResourceUpdate(value);
    context.renderController.refreshHeaderStats();
};

export { handleDecodedHardwareSnapshotRenderEvent, handleHardwareProcessRenderEvent, handleHardwareSnapshotRenderEvent };
export type { HardwareRealtimeRenderEventContext };
