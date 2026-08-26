/* SoAI - Abort-aware timer delay primitive [frontend/assets/ts/core/concurrency/timerDelay.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const waitForTimerDelay = async (windowRef: Window | null, delayMs: number, signal: AbortSignal | null): Promise<void> => {
    await new Promise<void>((resolve) => {
        if (windowRef === null || signal?.aborted === true) {
            resolve();
            return;
        }
        let timeoutId: number | null = null;
        const cleanupAndResolve = (): void => {
            if (timeoutId !== null) {
                windowRef.clearTimeout(timeoutId);
            }
            signal?.removeEventListener('abort', cleanupAndResolve);
            resolve();
        };
        timeoutId = windowRef.setTimeout(cleanupAndResolve, delayMs);
        signal?.addEventListener('abort', cleanupAndResolve, { once: true });
    });
};

export { waitForTimerDelay };
