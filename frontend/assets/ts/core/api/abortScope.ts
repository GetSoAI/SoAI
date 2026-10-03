/* SoAI - Frontend API request abort ownership [frontend/assets/ts/core/api/abortScope.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface ApiAbortScope {
    readonly signal: AbortSignal;
    readonly timeoutTriggered: boolean;
    refreshTimeout(): void;
    cleanup(): void;
}

const createAbortScope = (externalSignal: AbortSignal | undefined, timeoutMs: number): ApiAbortScope => {
    const abortController = new AbortController();
    let externalAbortHandler: (() => void) | null = null;
    let timeoutTriggered = false;
    let cleaned = false;
    let timeoutId: ReturnType<typeof setTimeout>;
    const startTimeout = (): void => {
        timeoutId = setTimeout(() => {
            if (abortController.signal.aborted) {
                return;
            }
            timeoutTriggered = true;
            abortController.abort();
        }, timeoutMs);
    };
    if (externalSignal) {
        if (externalSignal.aborted) {
            abortController.abort();
        } else {
            externalAbortHandler = (): void => {
                abortController.abort();
            };
            externalSignal.addEventListener('abort', externalAbortHandler, { once: true });
        }
    }
    startTimeout();
    return {
        signal: abortController.signal,
        get timeoutTriggered(): boolean {
            return timeoutTriggered;
        },
        refreshTimeout(): void {
            if (cleaned || abortController.signal.aborted) {
                return;
            }
            clearTimeout(timeoutId);
            startTimeout();
        },
        cleanup(): void {
            if (cleaned) {
                return;
            }
            cleaned = true;
            clearTimeout(timeoutId);
            if (externalAbortHandler && externalSignal) {
                externalSignal.removeEventListener('abort', externalAbortHandler);
            }
        }
    };
};

export { createAbortScope };
export type { ApiAbortScope };
