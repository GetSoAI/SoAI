/* SoAI - Promise-based delay primitive [frontend/assets/ts/core/primitives/sleepMs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindow } from '@core/environment/public.ts';

const sleepMs = async (delayMs: number): Promise<void> => {
    const safeDelay = Number.isFinite(delayMs) ? Math.max(0, delayMs) : 0;
    await new Promise<void>((resolve) => {
        getWindow().setTimeout(resolve, safeDelay);
    });
};

export { sleepMs };
