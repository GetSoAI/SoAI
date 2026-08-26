/* SoAI - Hardware page GPU control label manager [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlLabelManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { GpuControlType } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

export const resolveGpuControlLabel = (type: GpuControlType): string => {
    switch (type) {
        case 'power':
            return i18n.t('hardware.gpu.controls.power_limit');
        case 'core':
            return i18n.t('hardware.gpu.controls.coreClock');
        case 'memory':
            return i18n.t('hardware.gpu.controls.memoryClock');
        case 'fan':
            return i18n.t('hardware.gpu.controls.fan_speed');
        default:
            return i18n.t('common.unknown');
    }
};
