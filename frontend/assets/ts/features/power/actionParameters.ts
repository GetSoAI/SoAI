/* SoAI - Power action parameter conversion [frontend/assets/ts/features/power/actionParameters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readPositiveFlooredIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import type { ActionParameters } from '@features/power/contracts.ts';

const parseDelayMs = (parameters: ActionParameters): number => {
    return (readPositiveFlooredIntegerOrNullValue(parameters.delay) ?? 0) * 1000;
};

const buildForceDelayOptions = (parameters: ActionParameters): { force?: boolean; delay?: number } => {
    const delay = parseDelayMs(parameters);
    if (typeof parameters.force === 'boolean') {
        return { force: parameters.force, delay };
    }
    return { delay };
};

export { buildForceDelayOptions, parseDelayMs };
