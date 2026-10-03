/* SoAI - SoAI Bench run collection and page-visit state [frontend/assets/ts/features/hardware/modals/soaibenchrun/sessionState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { i18n } from '@core/i18n/index.ts';
import type { DecodedSoAIBenchRun } from '@core/realtime/streammanager/resources/soaibenchRunsResource.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isActiveSoAIBenchRun, isCertifiedSoAIBenchRun, isTerminalSoAIBenchStatus, presentDecodedRunRecord } from '@features/hardware/modals/soaibenchrun/mappers.ts';
import { isSoAIBenchRunEntryActive, resolveSoAIBenchActivityState, resolveSoAIBenchRunPhase } from '@features/hardware/modals/soaibenchrun/runPhase.ts';
import type { SoAIBenchActivityState, SoAIBenchRunEntry, SoAIBenchRunOpenRequest, SoAIBenchRunRecord, SoAIBenchRunsFreshness } from '@features/hardware/modals/soaibenchrun/types.ts';
import { getSoAIBenchNotAvailableLabel } from '@features/hardware/soaibenchMetricFormatting.ts';
import { getDeletedSoAIBenchRunIds, getSoAIBenchRunById, getSoAIBenchRuns, hasSoAIBenchHistoryForDevice } from '@features/hardware/soaibenchRunsIndex.ts';

interface SoAIBenchRunReconciliation {
    changed: ReadonlySet<string>;
    missing: readonly SoAIBenchRunEntry[];
}

class SoAIBenchRunSessionState {
    readonly #visit = new SequenceToken();
    readonly #entries: SoAIBenchRunEntry[] = [];
    readonly #entriesByRunId = new Map<string, SoAIBenchRunEntry>();
    readonly #startsByDevice = new Map<string, SoAIBenchRunEntry>();
    readonly #deletedRunIds = new Set<string>();
    readonly #verifiedMissingRunIds = new Set<string>();
    #sectionSequence = 0;
    #runsPayload: JsonObject | null = null;
    gpuOptions: readonly SoAIBenchRunOpenRequest[] = [];
    freshness: SoAIBenchRunsFreshness = { live: true, updatedAtMs: null };

    get visit(): number {
        return this.#visit.value;
    }

    isVisitActive(visit: number): boolean {
        return this.#visit.isActive(visit);
    }

    get runsPayload(): JsonObject | null {
        return this.#runsPayload;
    }

    entries(): readonly SoAIBenchRunEntry[] {
        return this.#entries;
    }

    findEntry(sectionId: string): SoAIBenchRunEntry | null {
        return this.#entries.find((entry) => entry.sectionId === sectionId) ?? null;
    }

    requireEntry(sectionId: string): SoAIBenchRunEntry {
        const entry = this.findEntry(sectionId);
        if (entry === null) {
            throw new Error('SoAIBench run section is no longer available');
        }
        return entry;
    }

    requireRunEntry(runId: string): SoAIBenchRunEntry {
        const entry = this.#entriesByRunId.get(runId);
        if (entry === undefined) {
            throw new Error('SoAIBench run is no longer available');
        }
        return entry;
    }

    activeEntryForDevice(deviceId: string | null): SoAIBenchRunEntry | null {
        return deviceId === null ? null : (this.#entries.find((entry) => entry.request.deviceId === deviceId && isSoAIBenchRunEntryActive(entry)) ?? null);
    }

    deviceActivity(deviceId: string | null): SoAIBenchActivityState | null {
        const entry = this.activeEntryForDevice(deviceId);
        return entry === null ? null : resolveSoAIBenchActivityState(resolveSoAIBenchRunPhase(entry));
    }

    hasActivity(): boolean {
        return this.#entries.some((entry) => isSoAIBenchRunEntryActive(entry));
    }

    activitySignature(): string {
        const active = this.#entries.flatMap((entry) => {
            const state = resolveSoAIBenchActivityState(resolveSoAIBenchRunPhase(entry));
            return state === null ? [] : [`${entry.request.deviceId}:${state}`];
        });
        return `${String(this.#entries.length > 0)}|${active.join(',')}`;
    }

    hasHistory(deviceId: string): boolean {
        return hasSoAIBenchHistoryForDevice(this.#runsPayload, deviceId);
    }

    isStartPending(entry: SoAIBenchRunEntry): boolean {
        return this.#startsByDevice.get(entry.request.deviceId) === entry;
    }

    currentRequest(entry: SoAIBenchRunEntry): SoAIBenchRunOpenRequest {
        return this.#inventoryRequest(entry.request.deviceId) ?? entry.request;
    }

    beginStart(request: SoAIBenchRunOpenRequest, reuse: SoAIBenchRunEntry | null): SoAIBenchRunEntry | null {
        if (this.activeEntryForDevice(request.deviceId) !== null || (reuse !== null && (reuse.runId !== null || !this.#entries.includes(reuse)))) {
            return null;
        }
        const entry = reuse ?? this.#append(request, null);
        entry.createdAtMs = Date.now();
        entry.run = null;
        entry.stopPending = false;
        entry.settlement = 'open';
        entry.reason = null;
        entry.recovering = false;
        this.#startsByDevice.set(request.deviceId, entry);
        return entry;
    }

    finishStart(entry: SoAIBenchRunEntry): void {
        if (this.isStartPending(entry)) {
            this.#startsByDevice.delete(entry.request.deviceId);
        }
    }

    bindRun(entry: SoAIBenchRunEntry, runId: string): SoAIBenchRunEntry {
        const existing = this.#entriesByRunId.get(runId);
        if (existing !== undefined && existing !== entry) {
            this.#discard(entry);
            return existing;
        }
        if (entry.runId !== null && entry.runId !== runId) {
            this.#entriesByRunId.delete(entry.runId);
            entry.run = null;
        }
        entry.runId = runId;
        entry.settlement = 'open';
        entry.reason = null;
        this.#entriesByRunId.set(runId, entry);
        return entry;
    }

    applyRun(run: SoAIBenchRunRecord): SoAIBenchRunEntry | null {
        if (this.#deletedRunIds.has(run.runId)) {
            return null;
        }
        const entry = this.#entriesByRunId.get(run.runId) ?? this.#adopt(run);
        if (entry === null || (entry.run !== null && run.updateSeq <= entry.run.updateSeq)) {
            return null;
        }
        entry.run = run;
        entry.settlement = 'open';
        entry.reason = null;
        entry.recovering = false;
        if (isTerminalSoAIBenchStatus(run.status)) {
            entry.stopPending = false;
        }
        return entry;
    }

    reconcile(payload: JsonObject): SoAIBenchRunReconciliation {
        this.#runsPayload = payload;
        for (const runId of getDeletedSoAIBenchRunIds(payload)) {
            this.removeRun(runId);
        }
        const changed = new Set<string>();
        const runs = getSoAIBenchRuns(payload);
        for (let index = runs.length - 1; index >= 0; index -= 1) {
            const decoded = runs[index];
            if (decoded === undefined || !this.#isRelevant(decoded)) {
                continue;
            }
            const entry = this.applyRun(presentDecodedRunRecord(decoded));
            if (entry !== null) {
                changed.add(entry.sectionId);
            }
        }
        const missing: SoAIBenchRunEntry[] = [];
        for (const entry of this.#entries) {
            if (entry.runId === null || !isSoAIBenchRunEntryActive(entry)) {
                continue;
            }
            if (getSoAIBenchRunById(payload, entry.runId) !== null) {
                this.#verifiedMissingRunIds.delete(entry.runId);
                if (entry.settlement === 'unresolved') {
                    entry.settlement = 'open';
                    entry.reason = null;
                    changed.add(entry.sectionId);
                }
            } else if (entry.settlement === 'open' && !entry.recovering && !this.#verifiedMissingRunIds.has(entry.runId)) {
                missing.push(entry);
            }
        }
        return { changed, missing };
    }

    requestStop(entry: SoAIBenchRunEntry): boolean {
        if (resolveSoAIBenchRunPhase(entry) !== 'running') {
            return false;
        }
        entry.stopPending = true;
        return true;
    }

    releaseStop(entry: SoAIBenchRunEntry): void {
        entry.stopPending = false;
    }

    beginRecovery(entry: SoAIBenchRunEntry): void {
        entry.recovering = true;
    }

    completeRecovery(entry: SoAIBenchRunEntry, run: SoAIBenchRunRecord): void {
        this.#verifiedMissingRunIds.add(run.runId);
        entry.recovering = false;
        entry.settlement = 'open';
        entry.reason = null;
        this.applyRun(run);
    }

    reject(entry: SoAIBenchRunEntry, reason: string): void {
        entry.settlement = 'rejected';
        entry.reason = reason;
        entry.recovering = false;
    }

    markUnresolved(entry: SoAIBenchRunEntry, reason: string): void {
        entry.settlement = 'unresolved';
        entry.reason = reason;
        entry.recovering = false;
    }

    removeRun(runId: string): boolean {
        this.#deletedRunIds.add(runId);
        const entry = this.#entriesByRunId.get(runId);
        if (entry === undefined) {
            return false;
        }
        this.#discard(entry);
        return true;
    }

    reset(): void {
        this.#visit.invalidate();
        this.#entries.length = 0;
        this.#entriesByRunId.clear();
        this.#startsByDevice.clear();
        this.#deletedRunIds.clear();
        this.#verifiedMissingRunIds.clear();
        this.#runsPayload = null;
        this.gpuOptions = [];
    }

    #isRelevant(run: DecodedSoAIBenchRun): boolean {
        const tracked = this.#entriesByRunId.get(run.runId);
        if (tracked !== undefined) {
            return tracked.run === null || run.updateSeq > tracked.run.updateSeq;
        }
        return !this.#deletedRunIds.has(run.runId) && isCertifiedSoAIBenchRun(run) && isActiveSoAIBenchRun(run) && !isTerminalSoAIBenchStatus(run.status);
    }

    #adopt(run: SoAIBenchRunRecord): SoAIBenchRunEntry | null {
        if (!isCertifiedSoAIBenchRun(run) || !run.active || isTerminalSoAIBenchStatus(run.status)) {
            return null;
        }
        const unbound = this.#entries.find((entry) => entry.request.deviceId === run.deviceId && entry.runId === null && (this.isStartPending(entry) || entry.settlement === 'unresolved'));
        const request = this.#inventoryRequest(run.deviceId) ?? { deviceId: run.deviceId, gpuIndex: run.gpuIndex ?? getSoAIBenchNotAvailableLabel(), gpuName: run.gpuName ?? i18n.t('common.unknown') };
        return this.bindRun(unbound ?? this.#append(request, run.startedAtMs), run.runId);
    }

    #inventoryRequest(deviceId: string): SoAIBenchRunOpenRequest | null {
        return this.gpuOptions.find((candidate) => candidate.deviceId === deviceId) ?? null;
    }

    #append(request: SoAIBenchRunOpenRequest, startedAtMs: number | null): SoAIBenchRunEntry {
        this.#sectionSequence += 1;
        const entry: SoAIBenchRunEntry = { sectionId: `soaibench-run-${String(this.#visit.value)}-${String(this.#sectionSequence)}`, request, createdAtMs: startedAtMs ?? Date.now(), runId: null, run: null, stopPending: false, settlement: 'open', reason: null, recovering: false };
        this.#entries.push(entry);
        return entry;
    }

    #discard(entry: SoAIBenchRunEntry): void {
        const position = this.#entries.indexOf(entry);
        if (position >= 0) {
            this.#entries.splice(position, 1);
        }
        if (entry.runId !== null && this.#entriesByRunId.get(entry.runId) === entry) {
            this.#entriesByRunId.delete(entry.runId);
        }
        this.finishStart(entry);
    }
}

export { SoAIBenchRunSessionState };
