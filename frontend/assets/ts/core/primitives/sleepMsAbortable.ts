/* SoAI - Shared primitives sleep ms abortable [frontend/assets/ts/core/primitives/sleepMsAbortable.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindow } from '@core/environment/public.ts';

const sleepMsAbortable = async (signal: AbortSignal, delayMs: number): Promise<void> => {
    if (signal.aborted) {
        throw new DOMException('Aborted', 'AbortError');
    }

    const safeDelay = Number.isFinite(delayMs) ? Math.max(0, delayMs) : 0;
    const windowRef = getWindow();
    await new Promise<void>((resolve, reject) => {
        const timeoutId = windowRef.setTimeout(() => {
            signal.removeEventListener('abort', onAbort);
            resolve();
        }, safeDelay);

        const onAbort = (): void => {
            windowRef.clearTimeout(timeoutId);
            signal.removeEventListener('abort', onAbort);
            reject(new DOMException('Aborted', 'AbortError'));
        };

        signal.addEventListener('abort', onAbort, { once: true });
    });
};

export { sleepMsAbortable };
