/* SoAI - Automation page now line live updates [frontend/assets/ts/pages/automation/controllers/automationNowLineLiveUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveNowLineTopPx } from '@pages/automation/formatting/service.ts';
import { queryAutomationNowLines, queryAutomationNowTags } from '@pages/automation/dom.ts';
import type { AutomationViewMode } from '@pages/automation/types.ts';

interface AutomationNowLineLiveUpdatesDependencies {
    root: HTMLElement;
    hourHeightPx: number;
    getViewMode: () => AutomationViewMode;
    setTimeout: (callback: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null | undefined) => void;
}

const resolveLiveUpdateDelayMs = (viewMode: AutomationViewMode, now: Date): number => {
    if (viewMode === 'day' || viewMode === 'week') {
        return Math.max(16, 1000 - now.getMilliseconds());
    }
    const remainder = now.getTime() % 15000;
    return Math.max(250, 15000 - remainder);
};

const updateNowLineTop = (dependencies: AutomationNowLineLiveUpdatesDependencies, now: Date): void => {
    const topPx = resolveNowLineTopPx(dependencies.hourHeightPx, now);
    const lines = queryAutomationNowLines(dependencies.root);
    for (const element of lines) {
        element.style.setProperty('top', `${topPx}px`);
    }

    const tags = queryAutomationNowTags(dependencies.root);
    for (const element of tags) {
        element.style.setProperty('top', `${topPx}px`);
    }
};

const connectAutomationNowLineLiveUpdates = (dependencies: AutomationNowLineLiveUpdatesDependencies, signal: AbortSignal): void => {
    let timeoutId: number | null = null;

    const clearTimer = (): void => {
        if (timeoutId === null) return;
        dependencies.clearTimer(timeoutId);
        timeoutId = null;
    };

    const tick = (): void => {
        if (signal.aborted) return;
        const now = new Date();
        updateNowLineTop(dependencies, now);

        clearTimer();
        const delay = resolveLiveUpdateDelayMs(dependencies.getViewMode(), now);
        const scheduled = dependencies.setTimeout(tick, delay);
        timeoutId = scheduled === null ? null : scheduled;
    };

    const onAbort = (): void => {
        clearTimer();
        signal.removeEventListener('abort', onAbort);
    };

    signal.addEventListener('abort', onAbort);
    tick();
};

export { connectAutomationNowLineLiveUpdates };
