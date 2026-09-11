/* SoAI - Hardware page root click dispatch [frontend/assets/ts/pages/hardware/controllers/hardwareRootClickDispatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { HARDWARE_ACTION_DEVICE_SELECT, HARDWARE_ACTION_EXPORT, HARDWARE_ACTION_GPU_APPLY, HARDWARE_ACTION_GPU_RETRY, HARDWARE_ACTION_GPU_RESET, HARDWARE_ACTION_GPU_SAVE_MODE, HARDWARE_ACTION_GPU_SLOT, HARDWARE_ACTION_GPU_SOAIBENCH_HISTORY, HARDWARE_ACTION_GPU_SOAIBENCH_REOPEN, HARDWARE_ACTION_GPU_SOAIBENCH_STANDARD, HARDWARE_ACTION_GPU_SOAIBENCH_STOP, HARDWARE_ACTION_GPU_SOAIBENCH_STRESS, HARDWARE_ACTION_GPU_SOAIBENCH_TOGGLE, HARDWARE_ACTION_LOGS, HARDWARE_ACTION_MEMORY_SWAP_TOGGLE, HARDWARE_ACTION_PROCESS_KILL, HARDWARE_ACTION_PROCESS_SORT, HARDWARE_ACTION_SYSTEM_INFO_COPY, HARDWARE_ACTION_SYSTEM_INFO_DOWNLOAD, HARDWARE_ACTION_SYSTEM_INFO_OPEN, type HardwareActionId } from '@pages/hardware/actions.ts';

interface HardwareRootClickDispatchHost {
    navigateToLogs(): void;
    exportHistoryCsv(): Promise<void>;
    openSystemInfo(): Promise<void>;
    copySystemInfo(): Promise<void>;
    downloadSystemInfo(): Promise<void>;
    handleProcessSort(actionElement: HTMLElement): void;
    handleProcessKill(actionElement: HTMLElement): Promise<void>;
    handleMemorySwapToggle(): void;
    handleDeviceSelect(component: string, identifier: string): Promise<void>;
    handleGpuApply(gpuIndex: string): Promise<void>;
    handleGpuSoAIBenchStandard(gpuIndex: string): Promise<void>;
    handleGpuSoAIBenchStress(gpuIndex: string): Promise<void>;
    handleGpuSoAIBenchStop(gpuIndex: string): Promise<void>;
    handleGpuSoAIBenchHistory(gpuIndex: string): Promise<void>;
    handleGpuSoAIBenchReopen(gpuIndex: string): Promise<void>;
    handleGpuSoAIBenchToggle(gpuIndex: string): void;
    retryGpuResources(): Promise<void>;
    handleGpuReset(gpuIndex: string): Promise<void>;
    handleGpuSaveMode(event: MouseEvent, gpuIndex: string): void;
    handleGpuSlot(gpuIndex: string, slotId: string): Promise<void>;
}

const shouldPreventDefaultForAction = (action: HardwareActionId): boolean => {
    return action === HARDWARE_ACTION_GPU_RETRY || action === HARDWARE_ACTION_LOGS || action === HARDWARE_ACTION_EXPORT || action === HARDWARE_ACTION_SYSTEM_INFO_OPEN || action === HARDWARE_ACTION_SYSTEM_INFO_COPY || action === HARDWARE_ACTION_SYSTEM_INFO_DOWNLOAD || action === HARDWARE_ACTION_PROCESS_SORT || action === HARDWARE_ACTION_PROCESS_KILL || action === HARDWARE_ACTION_MEMORY_SWAP_TOGGLE || action === HARDWARE_ACTION_DEVICE_SELECT || action === HARDWARE_ACTION_GPU_APPLY || action === HARDWARE_ACTION_GPU_SOAIBENCH_STANDARD || action === HARDWARE_ACTION_GPU_SOAIBENCH_STRESS || action === HARDWARE_ACTION_GPU_SOAIBENCH_STOP || action === HARDWARE_ACTION_GPU_SOAIBENCH_HISTORY || action === HARDWARE_ACTION_GPU_SOAIBENCH_REOPEN || action === HARDWARE_ACTION_GPU_SOAIBENCH_TOGGLE || action === HARDWARE_ACTION_GPU_RESET || action === HARDWARE_ACTION_GPU_SAVE_MODE || action === HARDWARE_ACTION_GPU_SLOT;
};

const dispatchHardwareRootClickAction = async (inputArguments: { event: MouseEvent; actionElement: HTMLElement; action: HardwareActionId; host: HardwareRootClickDispatchHost }): Promise<boolean> => {
    const { event, actionElement, action, host } = inputArguments;
    if (shouldPreventDefaultForAction(action)) {
        event.preventDefault();
    }
    switch (action) {
        case HARDWARE_ACTION_LOGS: {
            host.navigateToLogs();
            return true;
        }
        case HARDWARE_ACTION_EXPORT: {
            await host.exportHistoryCsv();
            return true;
        }
        case HARDWARE_ACTION_SYSTEM_INFO_OPEN: {
            await host.openSystemInfo();
            return true;
        }
        case HARDWARE_ACTION_SYSTEM_INFO_COPY: {
            await host.copySystemInfo();
            return true;
        }
        case HARDWARE_ACTION_SYSTEM_INFO_DOWNLOAD: {
            await host.downloadSystemInfo();
            return true;
        }
        case HARDWARE_ACTION_PROCESS_SORT: {
            host.handleProcessSort(actionElement);
            return true;
        }
        case HARDWARE_ACTION_PROCESS_KILL: {
            await host.handleProcessKill(actionElement);
            return true;
        }
        case HARDWARE_ACTION_MEMORY_SWAP_TOGGLE: {
            host.handleMemorySwapToggle();
            return true;
        }
        case HARDWARE_ACTION_DEVICE_SELECT: {
            const component = actionElement.dataset['component'];
            const identifierEncoded = actionElement.dataset['identifier'];
            if (!component) {
                throw new Error('Hardware device selection requires data-component');
            }
            if (!identifierEncoded) {
                throw new Error('Hardware device selection requires data-identifier');
            }
            await host.handleDeviceSelect(component, decodeURIComponent(identifierEncoded));
            return true;
        }
        case HARDWARE_ACTION_GPU_APPLY: {
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU apply');
            await host.handleGpuApply(gpuIndex);
            return true;
        }
        case HARDWARE_ACTION_GPU_SOAIBENCH_STANDARD: {
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU SoAIBench');
            await host.handleGpuSoAIBenchStandard(gpuIndex);
            return true;
        }
        case HARDWARE_ACTION_GPU_SOAIBENCH_STRESS: {
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU SoAIBench stress');
            await host.handleGpuSoAIBenchStress(gpuIndex);
            return true;
        }
        case HARDWARE_ACTION_GPU_SOAIBENCH_STOP: {
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU SoAIBench stop');
            await host.handleGpuSoAIBenchStop(gpuIndex);
            return true;
        }
        case HARDWARE_ACTION_GPU_SOAIBENCH_HISTORY: {
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU SoAIBench history');
            await host.handleGpuSoAIBenchHistory(gpuIndex);
            return true;
        }
        case HARDWARE_ACTION_GPU_SOAIBENCH_REOPEN: {
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU SoAIBench reopen');
            await host.handleGpuSoAIBenchReopen(gpuIndex);
            return true;
        }
        case HARDWARE_ACTION_GPU_SOAIBENCH_TOGGLE: {
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU SoAIBench toggle');
            host.handleGpuSoAIBenchToggle(gpuIndex);
            return true;
        }
        case HARDWARE_ACTION_GPU_RETRY:
            await host.retryGpuResources();
            return true;
        case HARDWARE_ACTION_GPU_RESET: {
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU reset');
            await host.handleGpuReset(gpuIndex);
            return true;
        }
        case HARDWARE_ACTION_GPU_SAVE_MODE: {
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU save');
            host.handleGpuSaveMode(event, gpuIndex);
            return true;
        }
        case HARDWARE_ACTION_GPU_SLOT: {
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU slot');
            const slotId = requireTrimmedDataAttribute(actionElement, 'slotId', 'GPU slot');
            await host.handleGpuSlot(gpuIndex, slotId);
            return true;
        }
        default:
            return false;
    }
};

export { dispatchHardwareRootClickAction };
export type { HardwareRootClickDispatchHost };
