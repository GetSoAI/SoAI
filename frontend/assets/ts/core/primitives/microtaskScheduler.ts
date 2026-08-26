/* SoAI - Shared primitives microtask scheduler [frontend/assets/ts/core/primitives/microtaskScheduler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface MicrotaskSchedulerOptions {
    label?: string | undefined;
    isDisposed?: (() => boolean) | undefined;
}

const createMicrotaskScheduler = (task: () => void, options: MicrotaskSchedulerOptions = {}): (() => void) => {
    let queued = false;
    return (): void => {
        if (queued) {
            return;
        }
        if (options.isDisposed?.() === true) {
            return;
        }
        queued = true;
        queueMicrotask(() => {
            queued = false;
            if (options.isDisposed?.() === true) {
                return;
            }
            try {
                task();
            } catch (error) {
                errorHandler.error(options.label ?? 'MicrotaskScheduler', 'Scheduled microtask failed', ensureError(error));
            }
        });
    };
};

export { createMicrotaskScheduler };
export type { MicrotaskSchedulerOptions };
