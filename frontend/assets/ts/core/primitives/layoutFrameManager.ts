/* SoAI - Shared primitives layout frame manager [frontend/assets/ts/core/primitives/layoutFrameManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';

export interface LayoutFrameManager {
    queue: (callback: () => void) => void;
    cancel: () => void;
}

export const createLayoutFrameManager = (): LayoutFrameManager => {
    const requestAnimationFrame = getRequestAnimationFrame();
    const cancelAnimationFrame = getCancelAnimationFrame();
    let point: number | null = null;
    return {
        queue(callback: () => void): void {
            if (isNullOrUndefined(point))
                point = requestAnimationFrame(() => {
                    point = null;
                    callback();
                });
        },
        cancel(): void {
            if (!isNullOrUndefined(point)) {
                cancelAnimationFrame(point);
                point = null;
            }
        }
    };
};
