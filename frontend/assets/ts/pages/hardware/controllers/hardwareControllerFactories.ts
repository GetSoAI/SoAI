/* SoAI - Hardware page controller factories [frontend/assets/ts/pages/hardware/controllers/hardwareControllerFactories.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { GpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ApiService, GpuSettingsUpdatePayload, GpuSlotStorePayload } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';
import type { GpuSoAIBenchRunLookupPayload, GpuSoAIBenchStartPayload } from '@pages/hardware/controllers/gpucontrol/soaibench/types.ts';
import type { ProcessTableManagerDependencies } from '@pages/hardware/widgets/processes/types.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';

interface HardwareGpuApiFactoryDependencies {
    updateGpuDevice: (deviceId: string, payload: GpuSettingsUpdatePayload) => Promise<GpuOperationResponse>;
    startGpuSoAIBench: (deviceId: string, payload: GpuSoAIBenchStartPayload) => Promise<GpuOperationResponse>;
    stopGpuSoAIBench: (runId: string) => Promise<GpuOperationResponse>;
    runsGpuSoAIBench: (payload: GpuSoAIBenchRunLookupPayload) => Promise<GpuOperationResponse>;
    applyGpuSlot: (deviceId: string, slot: string, boot: boolean | undefined) => Promise<GpuOperationResponse>;
    storeGpuSlot: (deviceId: string, slot: string, payload: GpuSlotStorePayload) => Promise<GpuOperationResponse>;
}

interface HardwareProcessTableDependenciesFactoryDependencies {
    optionalHTMLElement: (selector: string, parent?: Element | null) => HTMLElement | null;
    updateText: (element: Element, text: string) => void;
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
    runWithBoundary: (boundaryKey: string, functionValue: () => Promise<void>) => Promise<void>;
    showNotification: (message: string, type: string, duration?: number) => void;
    killProcess: ProcessTableManagerDependencies['killProcess'];
    getLastSnapshot: () => HardwarePageSnapshot | null;
    onSortChanged: ProcessTableManagerDependencies['onSortChanged'];
}

function createHardwareGpuApi(dependencies: HardwareGpuApiFactoryDependencies): ApiService {
    return {
        hardware: {
            gpuSettings: {
                updateDevice: async (deviceId, payload) => dependencies.updateGpuDevice(deviceId, payload)
            },
            gpuSoAIBench: {
                start: async (deviceId, payload) => dependencies.startGpuSoAIBench(deviceId, payload),
                stop: async (runId) => dependencies.stopGpuSoAIBench(runId),
                runs: async (payload) => dependencies.runsGpuSoAIBench(payload)
            },
            gpuSlots: {
                apply: async (deviceId, slot, boot) => dependencies.applyGpuSlot(deviceId, slot, boot),
                store: async (deviceId, slot, payload) => dependencies.storeGpuSlot(deviceId, slot, payload)
            }
        }
    };
}

function createHardwareProcessTableDependencies(dependencies: HardwareProcessTableDependenciesFactoryDependencies): ProcessTableManagerDependencies {
    return {
        optionalHTMLElement: (selector: string, parent?: Element | null) => dependencies.optionalHTMLElement(selector, parent),
        updateText: (element: Element, text: string) => dependencies.updateText(element, text),
        getIconSync: (iconName: IconName, options?: IconOptions) => dependencies.getIconSync(iconName, options),
        runWithBoundary: (boundaryKey: string, functionValue: () => Promise<void>) => dependencies.runWithBoundary(boundaryKey, functionValue),
        showNotification: (message: string, type: string, duration?: number) => dependencies.showNotification(message, type, duration),
        killProcess: (pid, options) => dependencies.killProcess(pid, options),
        getLastSnapshot: () => {
            const platformValue = dependencies.getLastSnapshot()?.capabilities.platform;
            if (!platformValue?.trim()) {
                return null;
            }
            return { capabilities: { platform: platformValue.trim() } };
        },
        onSortChanged: (state) => dependencies.onSortChanged(state)
    };
}

export { createHardwareGpuApi, createHardwareProcessTableDependencies };
