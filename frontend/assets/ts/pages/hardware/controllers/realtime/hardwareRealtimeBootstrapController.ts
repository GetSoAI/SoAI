/* SoAI - Hardware page control layer realtime bootstrap controller [frontend/assets/ts/pages/hardware/controllers/realtime/hardwareRealtimeBootstrapController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { throwIfAborted } from '@core/errors/abort.ts';
import { handleChartHistoricalRequest, startHistoryStream, type HardwareHistoryRuntime, type HardwareHistoryStreamDependencies } from '@pages/hardware/controllers/realtime/effects.ts';
import { initializeMainChart } from '@pages/hardware/controllers/render/effects.ts';
import type { HardwareRenderController } from '@pages/hardware/controllers/renderController.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';

type HardwareChartBootstrapInput = {
    state: HardwarePageState;
    renderController: HardwareRenderController;
    historyStreamDependencies: HardwareHistoryStreamDependencies;
    historyRuntime: HardwareHistoryRuntime;
    signal: AbortSignal | null;
    resetView: boolean;
    sequence: number;
    getCurrentSequence: () => number;
    prepareRealtimeResources: (options: { signal?: AbortSignal | undefined }) => Promise<void>;
};

const runChartBootstrap = async (input: HardwareChartBootstrapInput): Promise<void> => {
    const signalOrUndefined = input.signal ?? undefined;
    const isCurrentBootstrap = (): boolean => input.sequence === input.getCurrentSequence();
    await input.prepareRealtimeResources({ signal: signalOrUndefined });
    throwIfAborted(input.signal);
    if (!isCurrentBootstrap()) return;
    if (!input.state.mainChart) {
        await initializeMainChart(input.renderController.chartContext, {
            signal: signalOrUndefined,
            onRequestHistoricalData: (timestamp: number): Promise<void> => handleChartHistoricalRequest(input.historyStreamDependencies, input.historyRuntime, timestamp)
        });
    }
    throwIfAborted(input.signal);
    if (!isCurrentBootstrap()) return;
    await startHistoryStream(input.historyStreamDependencies, input.historyRuntime, {
        resetView: input.resetView,
        signal: input.signal
    });
};

export { runChartBootstrap };
export type { HardwareChartBootstrapInput };
