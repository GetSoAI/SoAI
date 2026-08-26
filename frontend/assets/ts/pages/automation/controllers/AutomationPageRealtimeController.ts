/* SoAI - Automation page realtime controller [frontend/assets/ts/pages/automation/controllers/AutomationPageRealtimeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { AutomationRealtimeUpdate, AutomationRunActivityServiceContract, AutomationRunRecord, AutomationZone } from '@features/automation/public.ts';
import { buildAutomationBufferedWindowSignature, resolveBufferedAutomationWindow } from '@pages/automation/controllers/automationWindow.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

interface AutomationPageRealtimeControllerDependencies {
    runActivity: AutomationRunActivityServiceContract;
    getState: () => AutomationPageState;
    setState: (next: AutomationPageState) => void;
    getWindowSignature: () => string;
    refreshData: () => Promise<void>;
    queueRender: () => void;
    getRun: (runId: string) => Promise<AutomationRunRecord>;
    setRunningAutomationIds: (next: ReadonlySet<string>) => void;
    run: (operation: string, task: () => Promise<void> | void) => void;
}

class AutomationPageRealtimeController {
    readonly #dependencies: AutomationPageRealtimeControllerDependencies;
    readonly #pendingRunIds = new Set<string>();
    #refreshInFlight = false;
    #definitionsRequested = false;
    #connected = false;
    #lifecycleToken = 0;
    #unsubscribeActivity: (() => void) | null = null;
    #unsubscribeRealtime: (() => void) | null = null;
    readonly #onAbort = (): void => {
        this.disconnect();
    };

    constructor(dependencies: AutomationPageRealtimeControllerDependencies) {
        this.#dependencies = dependencies;
    }

    connect(signal: AbortSignal): void {
        if (signal.aborted || this.#connected) {
            return;
        }
        this.#lifecycleToken += 1;
        const lifecycleToken = this.#lifecycleToken;
        this.#connected = true;
        let unsubscribeActivity: (() => void) | null = null;
        let unsubscribeRealtime: (() => void) | null = null;
        try {
            unsubscribeActivity = this.#dependencies.runActivity.subscribe((snapshot) => {
                if (!this.#connected || this.#lifecycleToken !== lifecycleToken) {
                    return;
                }
                this.#dependencies.setRunningAutomationIds(snapshot.runningAutomationIds);
                this.#dependencies.queueRender();
            });
            unsubscribeRealtime = this.#dependencies.runActivity.subscribeRealtime((update) => {
                if (this.#lifecycleToken !== lifecycleToken) {
                    return;
                }
                this.#handleUpdate(update);
            });
            this.#unsubscribeActivity = unsubscribeActivity;
            this.#unsubscribeRealtime = unsubscribeRealtime;
            signal.addEventListener('abort', this.#onAbort, { once: true });
        } catch (error) {
            unsubscribeActivity?.();
            unsubscribeRealtime?.();
            this.#connected = false;
            this.#lifecycleToken += 1;
            this.#resetPendingWork();
            throw error;
        }
    }

    disconnect(): void {
        this.#unsubscribeActivity?.();
        this.#unsubscribeRealtime?.();
        this.#unsubscribeActivity = null;
        this.#unsubscribeRealtime = null;
        this.#connected = false;
        this.#lifecycleToken += 1;
        this.#resetPendingWork();
    }

    dispose(): void {
        this.disconnect();
    }

    #resetPendingWork(): void {
        this.#pendingRunIds.clear();
        this.#refreshInFlight = false;
        this.#definitionsRequested = false;
    }

    #handleUpdate(update: AutomationRealtimeUpdate): void {
        if (!this.#connected) {
            return;
        }
        if (update.updateType === 'automation-changed') {
            this.#definitionsRequested = true;
            this.#drainQueue();
            return;
        }
        this.#pendingRunIds.add(update.runId);
        this.#drainQueue();
    }

    #drainQueue(): void {
        if (this.#refreshInFlight || !this.#connected) {
            return;
        }
        const lifecycleToken = this.#lifecycleToken;
        this.#refreshInFlight = true;
        this.#dependencies.run('automation:realtime:apply', async () => {
            try {
                while (this.#connected && this.#lifecycleToken === lifecycleToken && (this.#definitionsRequested || this.#pendingRunIds.size > 0)) {
                    if (this.#definitionsRequested) {
                        this.#definitionsRequested = false;
                        await this.#dependencies.refreshData();
                        if (!this.#connected || this.#lifecycleToken !== lifecycleToken) {
                            return;
                        }
                        continue;
                    }
                    const runIds = Array.from(this.#pendingRunIds);
                    this.#pendingRunIds.clear();
                    let stateChanged = false;
                    for (const runId of runIds) {
                        const updated = await this.#applyRunUpdate(runId, lifecycleToken);
                        stateChanged = stateChanged || updated;
                    }
                    if (stateChanged) {
                        this.#dependencies.queueRender();
                    }
                }
            } finally {
                if (this.#lifecycleToken !== lifecycleToken) {
                    return;
                }
                this.#refreshInFlight = false;
                if (this.#connected && (this.#definitionsRequested || this.#pendingRunIds.size > 0)) {
                    this.#drainQueue();
                }
            }
        });
    }

    async #applyRunUpdate(runId: string, lifecycleToken: number): Promise<boolean> {
        let runRecord: AutomationRunRecord;
        try {
            runRecord = await this.#dependencies.getRun(runId);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (runtimeError instanceof APIError && runtimeError.status === 404) {
                if (!this.#connected || this.#lifecycleToken !== lifecycleToken) {
                    return false;
                }
                this.#definitionsRequested = true;
                return false;
            }
            throw runtimeError;
        }
        if (!this.#connected || this.#lifecycleToken !== lifecycleToken) {
            return false;
        }
        const state = this.#dependencies.getState();
        const bufferedWindow = resolveBufferedAutomationWindow(state);
        const nextWindowSignature = buildAutomationBufferedWindowSignature(state);
        if (this.#dependencies.getWindowSignature() !== nextWindowSignature) {
            return false;
        }
        if (runRecord.scheduledAtMs < bufferedWindow.fromUtcMs || runRecord.scheduledAtMs >= bufferedWindow.toUtcMs) {
            return false;
        }
        const existingIndex = state.zones.findIndex((zone) => {
            return zone.runId === runRecord.runId || (zone.automationId === runRecord.automationId && zone.scheduledAtMs === runRecord.scheduledAtMs);
        });
        const existingZone = existingIndex >= 0 ? (state.zones[existingIndex] ?? null) : null;
        const title = runRecord.title ?? existingZone?.title ?? null;
        const enabled = runRecord.enabled ?? existingZone?.enabled ?? null;
        if (title === null || enabled === null) {
            this.#definitionsRequested = true;
            return false;
        }
        const nextZone: AutomationZone = {
            automationId: runRecord.automationId,
            scheduledAtMs: runRecord.scheduledAtMs,
            title,
            enabled,
            color: runRecord.color,
            runId: runRecord.runId,
            status: runRecord.status,
            resultExcerpt: runRecord.resultExcerpt,
            statusMessage: runRecord.statusMessage,
            convId: runRecord.convId,
            startedAtActualMs: runRecord.startedAtActualMs,
            finishedAtMs: runRecord.finishedAtMs
        };
        const nextZones = state.zones.slice();
        if (existingIndex >= 0) {
            nextZones[existingIndex] = nextZone;
        } else {
            nextZones.push(nextZone);
        }
        nextZones.sort((left, right) => left.scheduledAtMs - right.scheduledAtMs);
        this.#dependencies.setState({ ...state, zones: nextZones });
        return true;
    }
}

export { AutomationPageRealtimeController };
