/* SoAI - Automation page realtime bridge into the page data owner [frontend/assets/ts/pages/automation/controllers/AutomationPageRealtimeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationRealtimeUpdate, AutomationRunActivityServiceContract } from '@features/automation/public.ts';

interface AutomationPageRealtimeDataPort {
    noteRunChanged(runId: string): void;
    noteDefinitionsChanged(): void;
    noteConnectionLost(): void;
    noteConnectionRestored(): void;
}

interface AutomationPageRealtimeControllerDependencies {
    runActivity: AutomationRunActivityServiceContract;
    data: AutomationPageRealtimeDataPort;
    queueRender: () => void;
    setRunningAutomationIds: (next: ReadonlySet<string>) => void;
}

class AutomationPageRealtimeController {
    readonly #dependencies: AutomationPageRealtimeControllerDependencies;
    #unsubscribers: (() => void)[] = [];
    readonly #onAbort = (): void => {
        this.disconnect();
    };

    constructor(dependencies: AutomationPageRealtimeControllerDependencies) {
        this.#dependencies = dependencies;
    }

    connect(signal: AbortSignal): void {
        if (signal.aborted || this.#unsubscribers.length > 0) {
            return;
        }
        try {
            this.#unsubscribers.push(
                this.#dependencies.runActivity.subscribe((snapshot) => {
                    this.#dependencies.setRunningAutomationIds(snapshot.runningAutomationIds);
                    this.#dependencies.queueRender();
                })
            );
            this.#unsubscribers.push(this.#dependencies.runActivity.subscribeRealtime((update) => this.#handleUpdate(update)));
            signal.addEventListener('abort', this.#onAbort, { once: true });
        } catch (error) {
            this.disconnect();
            throw error;
        }
    }

    disconnect(): void {
        this.#unsubscribers.splice(0).forEach((unsubscribe) => unsubscribe());
    }

    dispose(): void {
        this.disconnect();
    }

    #handleUpdate(update: AutomationRealtimeUpdate): void {
        const data = this.#dependencies.data;
        if (update.updateType === 'run-changed') {
            data.noteRunChanged(update.runId);
        } else if (update.updateType === 'automation-changed') {
            data.noteDefinitionsChanged();
        } else if (update.updateType === 'connection-lost') {
            data.noteConnectionLost();
        } else {
            data.noteConnectionRestored();
        }
    }
}

export { AutomationPageRealtimeController };
