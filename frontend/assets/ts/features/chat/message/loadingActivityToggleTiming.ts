/* SoAI - Chat feature loading activity toggle timing [frontend/assets/ts/features/chat/message/loadingActivityToggleTiming.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { isFunction } from '@core/typeGuards.ts';

const waitForAnimationFrame = (element: HTMLElement, callback: () => void): void => {
    if (element.ownerDocument.defaultView === null) {
        throw new Error('Document window is required for loading activity timing');
    }
    getRequestAnimationFrame()(callback);
};

const waitForDuration = async (element: HTMLElement, durationMs: number): Promise<void> => {
    const view = element.ownerDocument.defaultView;
    const deferred = createDeferred<void>();
    if (view === null || !isFunction(view.setTimeout)) {
        throw new Error('Window.setTimeout is required for loading activity timing');
    }
    view.setTimeout((): void => {
        deferred.resolve();
    }, durationMs);
    await deferred.promise;
};

export { waitForAnimationFrame, waitForDuration };
