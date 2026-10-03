/* SoAI - Hardware page interaction events [frontend/assets/ts/pages/hardware/controllers/interaction/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_DELETE_LOCAL_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_PUBLISH_ACTION, HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION, METRIC_CONFIG, type SoAIBenchHistoryPagePanel, type SystemInfoModal } from '@features/hardware/public.ts';
import { HARDWARE_ACTION_GPU_BOOT_TOGGLE, HARDWARE_ACTION_GPU_SLIDER_AUTO, HARDWARE_ACTION_GPU_SLIDER_INPUT, HARDWARE_ACTION_GPU_SOAIBENCH_SELECT, HARDWARE_ACTION_PROCESS_SORT, HARDWARE_ACTION_SYSTEM_INFO_ANONYMIZE, type HardwareActionId } from '@pages/hardware/actions.ts';
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
    soaibenchHistoryPagePanel: SoAIBenchHistoryPagePanel;
    openSoAIBenchGpuSelection: () => Promise<void>;
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
        if (action === HARDWARE_ACTION_GPU_SOAIBENCH_SELECT) {
            event.preventDefault();
            await dependencies.openSoAIBenchGpuSelection();
            return;
        }
        if (actionElement.closest('#hardware-soaibench-history-panel')) {
            if (action === HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION) {
                dependencies.soaibenchHistoryPagePanel.handleSortAction(actionElement);
                return;
            }
            if (action === HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_PUBLISH_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_DELETE_LOCAL_ACTION) {
                const runId = requireTrimmedDataAttribute(actionElement, 'runId', 'SoAIBench history row action');
                if (action === HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION) return dependencies.soaibenchHistoryPagePanel.copyRun(runId);
                if (action === HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION) return dependencies.soaibenchHistoryPagePanel.downloadRun(runId);
                if (action === HARDWARE_SOAIBENCH_HISTORY_ROW_PUBLISH_ACTION) return dependencies.soaibenchHistoryPagePanel.publishRun(runId);
                return dependencies.soaibenchHistoryPagePanel.deleteLocalRun(runId);
            }
        }
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
                retryHistory: () => dependencies.updateAndBootstrap(),
                handleDeviceSelect: async (component: string, identifier: string) => {
                    const preferredMetric = getDefaultMetricForDevice(component, METRIC_CONFIG);
                    const selectionValue = buildDeviceSelectionValue(component, identifier);
                    dependencies.applyDeviceSelectionWithUi(selectionValue, preferredMetric);
                    await dependencies.updateAndBootstrap();
                },
                gpuController: dependencies.gpuController
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
        if (dependencies.gpuController.isCertifiedRunLocked(gpuIndex)) return;
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
            if (dependencies.gpuController.isCertifiedRunLocked(gpuIndex)) return;
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
        if (action === HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION && actionElement.closest('#hardware-soaibench-history-panel')) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                dependencies.soaibenchHistoryPagePanel.handleSortAction(actionElement);
            }
            return;
        }
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
