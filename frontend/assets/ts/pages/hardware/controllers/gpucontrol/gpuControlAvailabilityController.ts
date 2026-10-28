/* SoAI - GPU input availability during operations and capability changes [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlAvailabilityController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { dom } from '@core/dom/dom.ts';
import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import { GPU_CONTROL_TYPES } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { getSliderElements } from '@pages/hardware/controllers/gpucontrol/gpuControlDomControls.ts';
import { isControlSupported } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/guards.ts';

const resolveGpuControlAvailability = (capabilities: GpuCapabilitiesByIndex | null, index: string | number, type: string, isAuto: boolean, pending: boolean, locked: boolean): { manualDisabled: boolean; toggleDisabled: boolean } => ({
    manualDisabled: pending || locked || !isControlSupported(capabilities, index, type, 'manual'),
    toggleDisabled: pending || locked || !isControlSupported(capabilities, index, type, isAuto ? 'manual' : 'auto')
});

const syncGpuControlInputAvailability = (document: Document, capabilities: GpuCapabilitiesByIndex | null, index: string | number, pending: boolean, locked: boolean, previewSlot: string | null): void => {
    for (const type of GPU_CONTROL_TYPES) {
        const { slider, toggle, valueTrigger, valueInput } = getSliderElements(document, index, type);
        const availability = resolveGpuControlAvailability(capabilities, index, type, toggle?.checked ?? false, pending, locked);
        for (const control of [slider, valueTrigger, valueInput]) {
            if (control) setControlDisabledState(control, availability.manualDisabled);
        }
        if (toggle) setControlDisabledState(toggle, availability.toggleDisabled);
    }
    const boot = dom.resolve(`#gpu-boot-toggle-${index}`, document);
    if (boot instanceof HTMLInputElement) setControlDisabledState(boot, pending || locked || previewSlot === null);
};

export { resolveGpuControlAvailability, syncGpuControlInputAvailability };
