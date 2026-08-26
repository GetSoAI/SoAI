/* SoAI - Shared frontend runtime animation frames [frontend/assets/ts/core/runtime/animationFrames.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { throwIfAborted } from '@core/errors/abort.ts';

const awaitAnimationFrame = async (abortSignal: AbortSignal | null, abortMessage: string): Promise<void> => {
    throwIfAborted(abortSignal, abortMessage);
    const requestAnimationFrame = getRequestAnimationFrame();
    await new Promise<void>((resolve) => {
        requestAnimationFrame(() => resolve());
    });
    throwIfAborted(abortSignal, abortMessage);
};

export { awaitAnimationFrame };
