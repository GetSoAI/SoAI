/* SoAI - Hardware page GPU control dirty surfaces controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlDirtySurfacesController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber } from '@core/typeGuards.ts';
import { GPU_CONTROLS_CONFIG, GPU_SLIDER_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { getSliderElements } from '@pages/hardware/controllers/gpucontrol/gpuControlDomControls.ts';
import type { GpuSettingsState, GpuSettingState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const settingStatesEqual = (left: GpuSettingState | null | undefined, right: GpuSettingState | null | undefined): boolean => {
    if (!left || !right || left.mode !== right.mode) {
        return false;
    }
    if (left.mode === 'auto') {
        return true;
    }
    return isFiniteNumber(left.value) && isFiniteNumber(right.value) && left.value === right.value;
};

export const syncGpuSliderChangeSurfaces = (document: Document, index: string | number, liveSettings: GpuSettingsState | null, normalizedSettings: GpuSettingsState | null): void => {
    GPU_SLIDER_CONFIG.forEach(({ type }) => {
        const { container } = getSliderElements(document, index, type);
        if (!container) {
            return;
        }
        const settingKey = GPU_CONTROLS_CONFIG[type].settingKey;
        const modified = !!(liveSettings && normalizedSettings && !settingStatesEqual(normalizedSettings[settingKey], liveSettings[settingKey]));
        container.classList.add('setting-change-surface');
        container.classList.toggle('modified', modified);
    });
};
