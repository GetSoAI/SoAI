/* SoAI - Hardware page support [frontend/assets/ts/pages/hardware/contracts/hardwarePageSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import type { HardwarePageStorage } from '@features/hardware/public.ts';
import type { SecurityService } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const STR_GPU = 'gpu';
const STR_CPU = 'cpu';
const STR_DISK = 'disk';
const STR_NETWORK = 'network';
const STR_USAGE = 'usage';
const STR_OHLC = 'ohlc';
const STR_AVG = 'avg';

const HIDDEN = CSS_CLASSES.HIDDEN;

interface HardwarePageDependencies {
    storage: HardwarePageStorage;
    security: SecurityService;
}

export { HIDDEN, STR_AVG, STR_CPU, STR_DISK, STR_GPU, STR_NETWORK, STR_OHLC, STR_USAGE };

export type { HardwarePageDependencies };
