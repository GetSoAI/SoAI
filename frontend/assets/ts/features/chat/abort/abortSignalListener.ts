/* SoAI - Chat feature abort signal listener [frontend/assets/ts/features/chat/abort/abortSignalListener.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';

const registerAbortListener = (signal: AbortSignal, onAbort: () => void): (() => void) => {
    if (!isFunction(signal.addEventListener) || !isFunction(signal.removeEventListener)) {
        throw new Error('AbortSignal event listener APIs are required');
    }
    let invoked = false;
    const handler = (): void => {
        if (invoked) {
            return;
        }
        invoked = true;
        onAbort();
    };
    if (signal.aborted) {
        handler();
        return (): void => {};
    }
    signal.addEventListener('abort', handler, { once: true });
    const dispose = (): void => {
        signal.removeEventListener('abort', handler);
    };
    if (signal.aborted) {
        dispose();
        handler();
        return (): void => {};
    }
    return dispose;
};

export { registerAbortListener };
