/* SoAI - Shared UI notification timer [frontend/assets/ts/core/ui/notifications/notificationTimer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requirePerformanceNow } from '@core/environment/public.ts';
import type { NotificationTimerControls } from '@core/ui/notifications/types.ts';

const createAutoDismissNotificationTimer = (options: { durationMs: number; dismiss: () => void }): NotificationTimerControls => {
    const now = requirePerformanceNow();
    let timer: ReturnType<typeof setTimeout> | null = null;
    let remainingMs = options.durationMs;
    let startedAtMs = now();
    let cleared = false;

    const clear = (): void => {
        cleared = true;
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
    };

    const pause = (): void => {
        if (!timer || cleared) {
            return;
        }
        clearTimeout(timer);
        timer = null;
        remainingMs = Math.max(0, remainingMs - (now() - startedAtMs));
    };

    const resume = (): void => {
        if (cleared || timer) {
            return;
        }
        if (remainingMs <= 0) {
            options.dismiss();
            return;
        }
        startedAtMs = now();
        timer = setTimeout(options.dismiss, remainingMs);
    };

    resume();

    return { clear, pause, resume };
};

export { createAutoDismissNotificationTimer };
