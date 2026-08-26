/* SoAI - Automation page UI connections controller [frontend/assets/ts/pages/automation/controllers/AutomationPageUiConnectionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { AutomationCalendarPagerController } from '@pages/automation/controllers/AutomationCalendarPagerController.ts';
import { AutomationMonthLayoutController } from '@pages/automation/controllers/AutomationMonthLayoutController.ts';
import { connectAutomationNowLineLiveUpdates } from '@pages/automation/controllers/automationNowLineLiveUpdates.ts';
import { AutomationSplitterController } from '@pages/automation/controllers/AutomationSplitterController.ts';
import { AutomationTimeGridInteractionController } from '@pages/automation/controllers/AutomationTimeGridInteractionController.ts';
import { AUTOMATION_SPLIT_MAX_PERCENT, AUTOMATION_SPLIT_MIN_PERCENT } from '@pages/automation/state/preferences.ts';
import type { AutomationUiRefs, AutomationViewMode } from '@pages/automation/types.ts';

interface AutomationPageUiConnectionsControllerDependencies {
    ui: AutomationUiRefs;
    getViewMode: () => AutomationViewMode;
    getInitialSplitPercent: () => number;
    setSplitPercent: (value: number) => void;
    commitSplitPercent: (value: number) => void;
    openCreateModalAt: (utcMs: number) => void;
    hourHeightPx: number;
    requestAnimationFrame: (callback: () => void) => number;
    setTimeout: (callback: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null | undefined) => void;
    setMonthMaxChipsPerDay: (value: number) => void;
    queueRender: () => void;
    shiftVisiblePeriod: (offset: number) => Promise<void>;
}

class AutomationPageUiConnectionsController {
    readonly #dependencies: AutomationPageUiConnectionsControllerDependencies;
    readonly #pager: AutomationCalendarPagerController;
    #splitter: AutomationSplitterController | null = null;
    #timeGridInteractions: AutomationTimeGridInteractionController | null = null;
    #monthLayoutController: AutomationMonthLayoutController | null = null;
    #connectionAbortController: AbortController | null = null;
    #connected = false;
    readonly #onAbort = (): void => {
        this.destroy();
    };

    constructor(dependencies: AutomationPageUiConnectionsControllerDependencies) {
        this.#dependencies = dependencies;
        this.#pager = new AutomationCalendarPagerController({
            calendarRoot: dependencies.ui.calendarRoot,
            requestShift: (offset) => this.#dependencies.shiftVisiblePeriod(offset),
            requestAnimationFrame: (callback) => this.#dependencies.requestAnimationFrame(callback),
            setTimeout: (callback, delay) => this.#dependencies.setTimeout(callback, delay),
            clearTimer: (timerId) => this.#dependencies.clearTimer(timerId)
        });
    }

    connect(signal: AbortSignal): void {
        if (signal.aborted || this.#connected) {
            return;
        }
        const connectionAbortController = new AbortController();
        const connectionSignal = connectionAbortController.signal;
        this.#connectionAbortController = connectionAbortController;
        try {
            this.#pager.connect(connectionSignal);
            this.#splitter = new AutomationSplitterController({
                root: this.#dependencies.ui.root,
                splitter: this.#dependencies.ui.splitter,
                getInitialPercent: () => this.#dependencies.getInitialSplitPercent(),
                setPercent: (value) => this.#dependencies.setSplitPercent(value),
                commitPercent: (value) => this.#dependencies.commitSplitPercent(value),
                clampPercent: (value) => clampNumber(value, AUTOMATION_SPLIT_MIN_PERCENT, AUTOMATION_SPLIT_MAX_PERCENT)
            });
            this.#splitter.connect(connectionSignal);

            this.#monthLayoutController = new AutomationMonthLayoutController({
                root: this.#dependencies.ui.root,
                calendarRoot: this.#dependencies.ui.calendarRoot,
                requestAnimationFrame: (callback) => this.#dependencies.requestAnimationFrame(callback),
                getViewMode: () => this.#dependencies.getViewMode(),
                applyMaxChipsPerDay: (value) => this.#dependencies.setMonthMaxChipsPerDay(value),
                queueRender: () => this.#dependencies.queueRender()
            });
            this.#monthLayoutController.connect(connectionSignal);

            this.#timeGridInteractions = new AutomationTimeGridInteractionController({
                ui: this.#dependencies.ui,
                openCreateModalAt: (utcMs) => this.#dependencies.openCreateModalAt(utcMs),
                hourHeightPx: this.#dependencies.hourHeightPx
            });
            this.#timeGridInteractions.connect(connectionSignal);
            connectAutomationNowLineLiveUpdates(
                {
                    root: this.#dependencies.ui.root,
                    hourHeightPx: this.#dependencies.hourHeightPx,
                    getViewMode: () => this.#dependencies.getViewMode(),
                    setTimeout: (callback, delay) => this.#dependencies.setTimeout(callback, delay),
                    clearTimer: (timerId) => this.#dependencies.clearTimer(timerId)
                },
                connectionSignal
            );
            this.#connected = true;
            signal.addEventListener('abort', this.#onAbort, { once: true });
        } catch (error) {
            this.destroy();
            throw error;
        }
    }

    requestCenterNowLineAfterNextRender(): void {
        this.#pager.requestCenterNowAfterNextRender();
    }

    centerNowLineNow(): void {
        this.#pager.centerNowNow();
    }

    requestCenterPeriodAfterNextRender(): void {
        this.#pager.requestCenterPeriodAfterNextRender();
    }

    animateVisiblePeriod(direction: -1 | 1): Promise<void> {
        return this.#pager.animateVisiblePeriod(direction);
    }

    measureMonthLayout(): boolean {
        const monthLayoutController = this.#monthLayoutController;
        return monthLayoutController ? monthLayoutController.measureFromDom() : false;
    }

    afterRender(): void {
        this.#pager.syncFromDom();
    }

    destroy(): void {
        this.#connected = false;
        this.#connectionAbortController?.abort();
        this.#connectionAbortController = null;
        this.#pager.disconnect();
        this.#splitter?.destroy();
        this.#splitter = null;
        this.#timeGridInteractions?.destroy();
        this.#timeGridInteractions = null;
        this.#monthLayoutController?.destroy();
        this.#monthLayoutController = null;
    }

    cancelPendingScrollShift(): void {
        this.#pager.cancelPendingCommit();
    }
}

export { AutomationPageUiConnectionsController };
