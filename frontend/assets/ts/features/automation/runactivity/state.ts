/* SoAI - Automation feature run activity state [frontend/assets/ts/features/automation/runactivity/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationRunActivitySnapshot, AutomationRunStatus } from '@features/automation/runactivity/types.ts';
import type { AutomationRunRecord } from '@features/automation/runactivity/parsing.ts';

const ACTIVE_AUTOMATION_RUN_STATUSES: ReadonlySet<AutomationRunStatus> = new Set(['queued', 'running']);

class AutomationRunActivityState {
    readonly #runIdToAutomationId = new Map<string, string>();
    readonly #activeRunIds = new Set<string>();
    readonly #activeAutomationCounts = new Map<string, number>();
    #initialized = false;

    getSnapshot(): AutomationRunActivitySnapshot {
        return {
            initialized: this.#initialized,
            hasRunning: this.#activeRunIds.size > 0,
            runningAutomationIds: new Set(this.#activeAutomationCounts.keys())
        };
    }

    markInitialized(): void {
        this.#initialized = true;
    }

    reset(): void {
        this.#runIdToAutomationId.clear();
        this.#activeRunIds.clear();
        this.#activeAutomationCounts.clear();
        this.#initialized = false;
    }

    applyRunUpdate(update: AutomationRunRecord): void {
        const { runId, automationId, status } = update;
        this.#runIdToAutomationId.set(runId, automationId);
        const isActive = ACTIVE_AUTOMATION_RUN_STATUSES.has(status);
        const wasActive = this.#activeRunIds.has(runId);
        if (isActive === wasActive) {
            return;
        }
        if (isActive) {
            this.#activeRunIds.add(runId);
            this.#incrementAutomationRunning(automationId);
            return;
        }
        this.#activeRunIds.delete(runId);
        this.#decrementAutomationRunning(automationId);
    }

    removeRun(runId: string): void {
        const automationId = this.#runIdToAutomationId.get(runId) ?? null;
        this.#runIdToAutomationId.delete(runId);
        if (this.#activeRunIds.delete(runId) && automationId) {
            this.#decrementAutomationRunning(automationId);
        }
    }

    #incrementAutomationRunning(automationId: string): void {
        const count = this.#activeAutomationCounts.get(automationId) ?? 0;
        this.#activeAutomationCounts.set(automationId, count + 1);
    }

    #decrementAutomationRunning(automationId: string): void {
        const count = this.#activeAutomationCounts.get(automationId) ?? 0;
        if (count <= 1) {
            this.#activeAutomationCounts.delete(automationId);
            return;
        }
        this.#activeAutomationCounts.set(automationId, count - 1);
    }
}

export { ACTIVE_AUTOMATION_RUN_STATUSES, AutomationRunActivityState };
