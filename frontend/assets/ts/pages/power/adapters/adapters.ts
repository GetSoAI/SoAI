/* SoAI - Power page adapters [frontend/assets/ts/pages/power/adapters/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readPositiveFlooredIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import type { ActionParameters } from '@pages/power/types.ts';

const parseDelaySeconds = (parameters: ActionParameters): number => {
    return readPositiveFlooredIntegerOrNullValue(parameters.delay) ?? 0;
};

const parseDelayMs = (parameters: ActionParameters): number => {
    return parseDelaySeconds(parameters) * 1000;
};

const buildForceDelayOptions = (parameters: ActionParameters): { force?: boolean; delay?: number } => {
    const delay = parseDelayMs(parameters);
    if (typeof parameters.force === 'boolean') {
        return { force: parameters.force, delay };
    }
    return { delay };
};

export { buildForceDelayOptions, parseDelayMs, parseDelaySeconds };
