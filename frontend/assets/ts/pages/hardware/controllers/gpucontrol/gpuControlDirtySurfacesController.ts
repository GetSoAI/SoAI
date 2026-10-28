/* SoAI - Hardware page GPU control dirty surfaces controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlDirtySurfacesController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { GPU_CONTROLS_CONFIG, GPU_SLIDER_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { setFieldSurfaceInvalid, setFieldSurfaceModified } from '@core/forms/fieldSurface.ts';
import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import { getSliderElements } from '@pages/hardware/controllers/gpucontrol/gpuControlDomControls.ts';
import { getOffsetControlContext, gpuSettingStatesEqual } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import { isGpuValueEditing, readGpuEditorValue } from '@pages/hardware/controllers/gpucontrol/gpuControlValueEditorController.ts';
import type { GpuSettingsState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

export const syncGpuSliderChangeSurfaces = (document: Document, index: string | number, liveSettings: GpuSettingsState | null, normalizedSettings: GpuSettingsState | null, capabilities: GpuCapabilitiesByIndex | null): void => {
    GPU_SLIDER_CONFIG.forEach(({ type }) => {
        const { container, valueInput } = getSliderElements(document, index, type);
        if (!container) {
            return;
        }
        const settingKey = GPU_CONTROLS_CONFIG[type].settingKey;
        const editing = valueInput !== undefined && isGpuValueEditing(valueInput);
        const value = editing ? readGpuEditorValue(capabilities, index, type, valueInput) : null;
        const invalid = editing && value === null;
        const candidate = value === null ? normalizedSettings?.[settingKey] : ({ mode: 'manual', value: value + (getOffsetControlContext(capabilities, index, type)?.defaultAbs ?? 0) } satisfies GpuSettingsState[typeof settingKey]);
        const modified = invalid || !!(liveSettings && candidate && !gpuSettingStatesEqual(candidate, liveSettings[settingKey]));
        container.classList.add('setting-change-surface');
        setFieldSurfaceModified(container, modified);
        setFieldSurfaceInvalid(container, invalid);
        valueInput?.setAttribute('aria-invalid', String(invalid));
    });
};
