/* SoAI - Hardware page interaction events [frontend/assets/ts/pages/hardware/controllers/interaction/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { METRIC_CONFIG, type SystemInfoModal } from '@features/hardware/public.ts';
import { HARDWARE_ACTION_GPU_BOOT_TOGGLE, HARDWARE_ACTION_GPU_SLIDER_AUTO, HARDWARE_ACTION_GPU_SLIDER_INPUT, HARDWARE_ACTION_PROCESS_SORT, HARDWARE_ACTION_SYSTEM_INFO_ANONYMIZE, type HardwareActionId } from '@pages/hardware/actions.ts';
import type { GpuControlManager } from '@pages/hardware/controllers/gpucontrol/GpuControlManager.ts';
import { dispatchHardwareRootClickAction } from '@pages/hardware/controllers/hardwareRootClickDispatch.ts';
import { buildDeviceSelectionValue, getDefaultMetricForDevice } from '@pages/hardware/state/hardwareSelection.ts';
import type { MemorySwapPanelController } from '@pages/hardware/widgets/memoryswap/MemorySwapPanelController.ts';
import type { ProcessTableManager } from '@pages/hardware/widgets/processes/service.ts';

type HardwareInteractionEventDependencies = {
    processController: ProcessTableManager;
    memorySwapController: MemorySwapPanelController;
    gpuController: GpuControlManager;
    systemInfoModal: SystemInfoModal;
    exportHistoryCsv: () => Promise<void>;
    applyDeviceSelectionWithUi: (value: string, preferredMetric: string | null) => void;
    updateAndBootstrap: () => Promise<void>;
    navigateToLogs: () => void;
};

type HardwareInteractionHandlers = {
    handleRootActionClick: (event: MouseEvent, action: HardwareActionId, actionElement: HTMLElement) => Promise<void>;
    handleRootClickMiss: (event: MouseEvent) => void;
    handleRootActionInput: (event: Event, action: HardwareActionId, actionElement: HTMLElement) => void;
    handleRootActionChange: (event: Event, action: HardwareActionId, actionElement: HTMLElement) => void;
    handleRootActionKeydown: (event: KeyboardEvent, action: HardwareActionId, actionElement: HTMLElement) => void;
};

const createHardwareInteractionHandlers = (dependencies: HardwareInteractionEventDependencies): HardwareInteractionHandlers => {
    const handleRootActionClick = async (event: MouseEvent, action: HardwareActionId, actionElement: HTMLElement): Promise<void> => {
        await dispatchHardwareRootClickAction({
            event,
            actionElement,
            action,
            host: {
                navigateToLogs: () => {
                    dependencies.navigateToLogs();
                },
                exportHistoryCsv: () => dependencies.exportHistoryCsv(),
                openSystemInfo: async () => await dependencies.systemInfoModal.open(),
                copySystemInfo: async () => await dependencies.systemInfoModal.copy(),
                downloadSystemInfo: async () => await dependencies.systemInfoModal.download(),
                handleProcessSort: (element: HTMLElement) => dependencies.processController.handleSortAction(element),
                handleProcessKill: async (element: HTMLElement) => {
                    await dependencies.processController.handleKillAction(element);
                },
                handleMemorySwapToggle: () => dependencies.memorySwapController.toggleMode(),
                handleDeviceSelect: async (component: string, identifier: string) => {
                    const preferredMetric = getDefaultMetricForDevice(component, METRIC_CONFIG);
                    const selectionValue = buildDeviceSelectionValue(component, identifier);
                    dependencies.applyDeviceSelectionWithUi(selectionValue, preferredMetric);
                    await dependencies.updateAndBootstrap();
                },
                handleGpuApply: async (gpuIndex: string) => await dependencies.gpuController.handleGpuApplyClick(gpuIndex),
                handleGpuSoAIBenchStandard: async (gpuIndex: string) => await dependencies.gpuController.handleGpuSoAIBenchStandardClick(gpuIndex),
                handleGpuSoAIBenchStress: async (gpuIndex: string) => await dependencies.gpuController.handleGpuSoAIBenchStressClick(gpuIndex),
                handleGpuSoAIBenchStop: async (gpuIndex: string) => await dependencies.gpuController.handleGpuSoAIBenchStopClick(gpuIndex),
                handleGpuSoAIBenchHistory: async (gpuIndex: string) => await dependencies.gpuController.handleGpuSoAIBenchHistoryClick(gpuIndex),
                handleGpuSoAIBenchReopen: async (gpuIndex: string) => await dependencies.gpuController.handleGpuSoAIBenchReopenClick(gpuIndex),
                handleGpuSoAIBenchToggle: (gpuIndex: string) => dependencies.gpuController.handleGpuSoAIBenchToggleClick(gpuIndex),
                retryGpuResources: () => dependencies.gpuController.retryResources(),
                handleGpuReset: async (gpuIndex: string) => await dependencies.gpuController.resetGpuSettings(gpuIndex),
                handleGpuSaveMode: (clickEvent: MouseEvent, gpuIndex: string) => {
                    dependencies.gpuController.handleGpuSaveButtonClick(clickEvent, gpuIndex);
                },
                handleGpuSlot: async (gpuIndex: string, slotId: string) => await dependencies.gpuController.handleGpuSlotClick(gpuIndex, slotId)
            }
        });
    };

    const handleRootClickMiss = (event: MouseEvent): void => {
        if (dependencies.gpuController?.hasActiveGpuSaveMode?.()) {
            dependencies.gpuController.handleGpuContainerClick(event);
        }
    };

    const handleRootActionInput = (event: Event, action: HardwareActionId, actionElement: HTMLElement): void => {
        void event;
        if (action !== HARDWARE_ACTION_GPU_SLIDER_INPUT) return;

        if (!(actionElement instanceof HTMLInputElement)) {
            throw new Error('GPU slider input must be an input element');
        }
        const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU slider input');
        const sliderType = requireTrimmedDataAttribute(actionElement, 'sliderType', 'GPU slider input');
        dependencies.gpuController.markGpuSettingsEdited(gpuIndex);
        dependencies.gpuController.setSliderToManual(gpuIndex, sliderType, actionElement.value);
        dependencies.gpuController.markGpuStateHydrated(gpuIndex);
        dependencies.gpuController.refreshApplyState(gpuIndex);
    };

    const handleRootActionChange = (event: Event, action: HardwareActionId, actionElement: HTMLElement): void => {
        if (action === HARDWARE_ACTION_SYSTEM_INFO_ANONYMIZE) {
            dependencies.systemInfoModal.handleAnonymizeToggle(event);
            return;
        }

        if (action === HARDWARE_ACTION_GPU_SLIDER_AUTO) {
            if (!(actionElement instanceof HTMLInputElement)) {
                throw new Error('GPU slider auto toggle must be an input element');
            }
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU slider auto toggle');
            const sliderType = requireTrimmedDataAttribute(actionElement, 'sliderType', 'GPU slider auto toggle');
            dependencies.gpuController.markGpuSettingsEdited(gpuIndex);
            dependencies.gpuController.updateSliderAutoState(gpuIndex, sliderType, actionElement.checked);
            dependencies.gpuController.markGpuStateHydrated(gpuIndex);
            dependencies.gpuController.refreshApplyState(gpuIndex);
            return;
        }

        if (action === HARDWARE_ACTION_GPU_BOOT_TOGGLE) {
            if (!(actionElement instanceof HTMLInputElement)) {
                throw new Error('GPU boot toggle must be an input element');
            }
            const gpuIndex = requireTrimmedDataAttribute(actionElement, 'gpuIndex', 'GPU boot toggle');
            dependencies.gpuController.handleGpuBootToggle(gpuIndex, actionElement.checked);
            return;
        }
    };

    const handleRootActionKeydown = (event: KeyboardEvent, action: HardwareActionId, actionElement: HTMLElement): void => {
        if (action !== HARDWARE_ACTION_PROCESS_SORT) return;
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            dependencies.processController.handleSortAction(actionElement);
        }
    };

    return {
        handleRootActionClick,
        handleRootClickMiss,
        handleRootActionInput,
        handleRootActionChange,
        handleRootActionKeydown
    };
};

export { createHardwareInteractionHandlers };
export type { HardwareInteractionEventDependencies, HardwareInteractionHandlers };
