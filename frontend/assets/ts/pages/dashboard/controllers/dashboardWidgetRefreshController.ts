/* SoAI - Dashboard page widget refresh controller [frontend/assets/ts/pages/dashboard/controllers/dashboardWidgetRefreshController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DashboardTimerControl } from '@core/edition/dashboardContribution.ts';

interface DashboardWidgetRefreshControllerDependencies {
    timers: DashboardTimerControl;
    intervalMs: number;
    onTick: () => void;
}

class DashboardWidgetRefreshController {
    readonly #timers: DashboardTimerControl;
    readonly #intervalMs: number;
    readonly #onTick: () => void;
    #timerId: number | null = null;

    constructor(dependencies: DashboardWidgetRefreshControllerDependencies) {
        this.#timers = dependencies.timers;
        this.#intervalMs = dependencies.intervalMs;
        this.#onTick = dependencies.onTick;
    }

    start(): void {
        if (this.#timerId !== null) {
            return;
        }
        this.#timerId = this.#timers.setTimer((): void => this.#onTick(), this.#intervalMs, { repeat: true });
    }

    stop(): void {
        this.#timers.clearTimer(this.#timerId);
        this.#timerId = null;
    }
}

export { DashboardWidgetRefreshController };
export type { DashboardWidgetRefreshControllerDependencies };
