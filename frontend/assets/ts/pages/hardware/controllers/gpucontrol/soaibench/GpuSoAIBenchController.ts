/* SoAI - GPU SoAI Bench run, history, and render coordination [frontend/assets/ts/pages/hardware/controllers/gpucontrol/soaibench/GpuSoAIBenchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { formatHashSignature } from '@core/realtime/streammanager/hashSignature.ts';
import { handleGpuSoAIBenchHistoryClick, handleGpuSoAIBenchRunClick, handleGpuSoAIBenchStartClick, handleGpuSoAIBenchStopClick } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/service.ts';
import { isSoAIBenchToggleDisabled } from '@pages/hardware/controllers/gpucontrol/soaibench/soaibenchRenderController.ts';
import type { ControlContext } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/types.ts';
import type { GpuUiState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

interface GpuSoAiBenchControllerDependencies {
    buildActionContext: () => ControlContext;
    ensureUiState: (index: string | number) => GpuUiState;
    handleRunsUpdate: (value: JsonValue) => void;
    syncSoAIBenchUi: (options?: { only?: string[] | null }) => void;
}

const str = String;

class GpuSoAIBenchController {
    readonly #dependencies: GpuSoAiBenchControllerDependencies;
    #runs: JsonValue = null;
    #runsRenderSignature = '';
    readonly #renderQueue: AnimationFrameRenderQueue<JsonValue>;

    constructor(dependencies: GpuSoAiBenchControllerDependencies) {
        this.#dependencies = dependencies;
        this.#renderQueue = new AnimationFrameRenderQueue<JsonValue>({
            label: 'Hardware SoAIBench GPU controls',
            render: () => this.#dependencies.syncSoAIBenchUi(),
            merge: (_previous, next) => next
        });
    }

    get runs(): JsonValue {
        return this.#runs;
    }

    setRuns(value: JsonValue): void {
        const signature = formatHashSignature(value);
        this.#runs = value;
        this.#dependencies.handleRunsUpdate(value);
        if (signature === this.#runsRenderSignature) {
            return;
        }
        this.#runsRenderSignature = signature;
        this.#renderQueue.schedule(value);
    }

    dispose(): void {
        this.#renderQueue.dispose();
    }

    async startStandard(index: string | number): Promise<void> {
        await handleGpuSoAIBenchRunClick(this.#dependencies.buildActionContext(), index);
    }

    async startStress(index: string | number): Promise<void> {
        await handleGpuSoAIBenchStartClick(this.#dependencies.buildActionContext(), index, 'stress');
    }

    async stop(index: string | number): Promise<void> {
        await handleGpuSoAIBenchStopClick(this.#dependencies.buildActionContext(), index);
    }

    async showHistory(index: string | number): Promise<void> {
        await handleGpuSoAIBenchHistoryClick(this.#dependencies.buildActionContext(), index);
    }

    async showRun(index: string | number): Promise<void> {
        await handleGpuSoAIBenchRunClick(this.#dependencies.buildActionContext(), index);
    }

    toggleActions(index: string | number): void {
        const key = str(index);
        const state = this.#dependencies.ensureUiState(key);
        if (isSoAIBenchToggleDisabled(state)) {
            return;
        }
        state.showSoAIBenchActions = true;
        this.#dependencies.syncSoAIBenchUi({ only: [key] });
    }
}

export { GpuSoAIBenchController };
