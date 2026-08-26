/* SoAI - File explorer page control layer task display controller [frontend/assets/ts/pages/fileexplorer/controllers/fileExplorerTaskDisplayController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { FileExplorerUiRefs } from '@pages/fileexplorer/types.ts';

interface FileExplorerTaskDisplayState {
    label: string;
    taskId: string;
}

const LABEL_UPDATE_INTERVAL_MS = 5000;

class FileExplorerTaskDisplayController {
    readonly #ui: FileExplorerUiRefs;
    readonly #fallbackLabel: string;
    readonly #timers = new ResourceTracker();
    #displayed: FileExplorerTaskDisplayState = { label: '', taskId: '-' };
    #pending: FileExplorerTaskDisplayState | null = null;
    #timerId: number | null = null;
    #lastAppliedAt = 0;

    constructor(ui: FileExplorerUiRefs, fallbackLabel: string) {
        this.#ui = ui;
        this.#fallbackLabel = fallbackLabel;
    }

    reset(): void {
        this.#clearTimer();
        this.#pending = null;
        this.#displayed = { label: '', taskId: '-' };
        this.#lastAppliedAt = 0;
        this.#apply({ label: this.#fallbackLabel, taskId: '-' });
    }

    sync(taskId: string, label: string): void {
        const nextState = { label: label || this.#fallbackLabel, taskId: taskId || '-' };
        if (nextState.label === this.#displayed.label && nextState.taskId === this.#displayed.taskId) {
            return;
        }
        if (nextState.taskId !== this.#displayed.taskId) {
            this.#clearTimer();
            this.#pending = null;
            this.#apply(nextState);
            return;
        }
        const now = performance.now();
        if (this.#displayed.label === '' || nextState.label === this.#fallbackLabel || now - this.#lastAppliedAt >= LABEL_UPDATE_INTERVAL_MS) {
            this.#clearTimer();
            this.#pending = null;
            this.#apply(nextState);
            return;
        }
        this.#pending = nextState;
        if (this.#timerId !== null) {
            return;
        }
        this.#timerId = this.#timers.setTimeout(
            (): void => {
                const pending = this.#pending;
                this.#clearTimer();
                this.#pending = null;
                if (pending) {
                    this.#apply(pending);
                }
            },
            Math.max(0, LABEL_UPDATE_INTERVAL_MS - (now - this.#lastAppliedAt))
        );
    }

    #apply(state: FileExplorerTaskDisplayState): void {
        this.#displayed = state;
        this.#lastAppliedAt = performance.now();
        this.#ui.taskLabel.textContent = state.label;
        this.#ui.taskId.textContent = state.taskId;
    }

    #clearTimer(): void {
        if (this.#timerId !== null) {
            this.#timers.clearTimeout(this.#timerId);
            this.#timerId = null;
        }
    }
}

export { FileExplorerTaskDisplayController };
