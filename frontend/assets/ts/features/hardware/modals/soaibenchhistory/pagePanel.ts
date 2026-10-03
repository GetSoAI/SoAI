/* SoAI - Hardware page SoAIBench run history [frontend/assets/ts/features/hardware/modals/soaibenchhistory/pagePanel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeGpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';
import { serializeGpuSoAIBenchHistoryRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { createMicrotaskScheduler } from '@core/primitives/microtaskScheduler.ts';
import { sleepMs } from '@core/primitives/sleepMs.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { requireSortableColumn } from '@core/ui/tables/sortableTable.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { copySoAIBenchRunExport, downloadSoAIBenchRunExport } from '@features/hardware/modals/soaibenchrun/exportActions.ts';
import { exportRunFromHistoryRun } from '@features/hardware/modals/soaibenchrun/exportText.ts';
import { setRunActionsDisabled } from '@features/hardware/modals/soaibenchhistory/dom.ts';
import { normalizeHistoryRuns } from '@features/hardware/modals/soaibenchhistory/mappers.ts';
import { PAGE_COLUMN_KEYS, renderPageHistoryTable, type PageHistoryEntry } from '@features/hardware/modals/soaibenchhistory/pageTableDom.ts';
import { HISTORY_SORT_DEFAULT_STATE, resolveNextHistorySortState, sortHistoryRuns, type SoAIBenchHistorySortState } from '@features/hardware/modals/soaibenchhistory/sorting.ts';
import type { SoAIBenchHistoryModalDependencies, SoAIBenchHistoryModalHost, SoAIBenchHistoryOpenRequest } from '@features/hardware/modals/soaibenchhistory/types.ts';
import { getSoAIBenchRuns } from '@features/hardware/soaibenchRunsIndex.ts';

const HISTORY_LIMIT = 100;
const READ_RETRY_DELAY_MS = 1200;

class SoAIBenchHistoryPagePanel {
    readonly #host: SoAIBenchHistoryModalHost;
    readonly #confirmDeleteLocalRun: SoAIBenchHistoryModalDependencies['confirmDeleteLocalRun'];
    readonly #deleteLocalRun: SoAIBenchHistoryModalDependencies['deleteLocalRun'];
    readonly #publishRun: SoAIBenchHistoryModalDependencies['publishRun'];
    readonly #busyRunIds = new Set<string>();
    readonly #entriesByDevice = new Map<string, readonly PageHistoryEntry[]>();
    readonly #failedDevices = new Set<string>();
    readonly #loadingDevices = new Set<string>();
    readonly #revisionByDevice = new Map<string, string>();
    readonly #requestTokenByDevice = new Map<string, number>();
    readonly #scheduleRender = createMicrotaskScheduler(() => this.#render(), { label: 'SoAIBenchHistoryPagePanel' });
    #devices = new Map<string, SoAIBenchHistoryOpenRequest>();
    #gpuOptions: readonly SoAIBenchHistoryOpenRequest[] = [];
    #streamRuns: ReturnType<typeof getSoAIBenchRuns> = [];
    #requestSerial = 0;
    #initialized = false;
    #sortState: SoAIBenchHistorySortState = HISTORY_SORT_DEFAULT_STATE;

    constructor({ host, confirmDeleteLocalRun, deleteLocalRun, publishRun }: SoAIBenchHistoryModalDependencies) {
        this.#host = host;
        this.#confirmDeleteLocalRun = confirmDeleteLocalRun;
        this.#deleteLocalRun = deleteLocalRun;
        this.#publishRun = publishRun;
    }

    setGpuOptions(options: readonly SoAIBenchHistoryOpenRequest[]): void {
        this.#gpuOptions = options;
        this.#sync();
    }

    setRuns(payload: JsonValue | null): void {
        this.#streamRuns = getSoAIBenchRuns(payload);
        this.#sync();
    }

    dispose(): void {
        this.#requestTokenByDevice.clear();
        this.#entriesByDevice.clear();
        this.#failedDevices.clear();
        this.#loadingDevices.clear();
        this.#revisionByDevice.clear();
        this.#devices.clear();
        this.#gpuOptions = [];
        this.#streamRuns = [];
        this.#busyRunIds.clear();
        this.#sortState = HISTORY_SORT_DEFAULT_STATE;
        this.#initialized = false;
    }

    handleSortAction(header: HTMLElement): void {
        const sortColumn = requireSortableColumn(PAGE_COLUMN_KEYS, header.dataset['sort'] ?? '', 'SoAIBench page history');
        this.#sortState = resolveNextHistorySortState(this.#sortState, sortColumn);
        this.#scheduleRender();
    }

    async copyRun(runId: string): Promise<void> {
        return this.#host.runWithBoundary('hardware:copySoAIBenchPageHistoryRun', async () => {
            const entry = this.#requireEntry(runId);
            await copySoAIBenchRunExport({ host: this.#host, request: entry.request, run: exportRunFromHistoryRun(entry.run) });
        });
    }

    async downloadRun(runId: string): Promise<void> {
        return this.#host.runWithBoundary('hardware:downloadSoAIBenchPageHistoryRun', async () => {
            const entry = this.#requireEntry(runId);
            downloadSoAIBenchRunExport({ host: this.#host, request: entry.request, run: exportRunFromHistoryRun(entry.run) });
        });
    }

    async publishRun(runId: string): Promise<void> {
        return this.#host.runWithBoundary('hardware:publishSoAIBenchPageHistoryRun', async () => {
            if (this.#busyRunIds.has(runId)) return;
            const entry = this.#requireEntry(runId);
            await this.#publishRun(entry.run, (disabled) => this.#setRunBusy(runId, disabled));
            const device = this.#devices.get(entry.request.deviceId);
            if (device) this.#reloadDevice(device);
        });
    }

    async deleteLocalRun(runId: string): Promise<void> {
        return this.#host.runWithBoundary('hardware:deleteLocalSoAIBenchPageHistoryRun', async () => {
            if (this.#busyRunIds.has(runId)) return;
            const entry = this.#requireEntry(runId);
            if (entry.run.status === 'running') throw new Error('Running SoAIBench history cannot be deleted');
            this.#setRunBusy(runId, true);
            try {
                if (!(await this.#confirmDeleteLocalRun())) return;
                await this.#deleteLocalRun(runId);
                this.#removeDeletedRun(entry.request.deviceId, runId);
            } finally {
                this.#setRunBusy(runId, false);
            }
        });
    }

    #removeDeletedRun(deviceId: string, runId: string): void {
        const deviceEntries = this.#entriesByDevice.get(deviceId);
        if (deviceEntries) {
            this.#entriesByDevice.set(
                deviceId,
                deviceEntries.filter((candidate) => candidate.run.runId !== runId)
            );
        }
        this.#streamRuns = this.#streamRuns.filter((run) => run.runId !== runId);
        this.#revisionByDevice.set(deviceId, this.#resolveRevisions().get(deviceId) ?? '');
        const device = this.#devices.get(deviceId);
        if (device && this.#loadingDevices.has(deviceId)) this.#startDeviceLoad(device);
        this.#scheduleRender();
        this.#sync();
    }

    #requireEntry(runId: string): PageHistoryEntry {
        for (const entries of this.#entriesByDevice.values()) {
            const entry = entries.find((candidate) => candidate.run.runId === runId);
            if (entry) return entry;
        }
        throw new Error(i18n.t('hardware.modals.soaibenchHistory.rowCopyUnavailable'));
    }

    #setRunBusy(runId: string, busy: boolean): void {
        if (busy) this.#busyRunIds.add(runId);
        else this.#busyRunIds.delete(runId);
        const root = dom.resolve('#hardware-soaibench-history-panel');
        if (root instanceof HTMLElement) setRunActionsDisabled(root, runId, busy);
    }

    #resolveDevices(): Map<string, SoAIBenchHistoryOpenRequest> {
        const devices = new Map(this.#gpuOptions.map((option) => [option.deviceId, option]));
        for (const run of this.#streamRuns) {
            if (devices.has(run.deviceId)) continue;
            devices.set(run.deviceId, {
                deviceId: run.deviceId,
                gpuIndex: String(run.gpuIdentity?.gpuIndex ?? 0),
                gpuName: toTrimmedString(run.gpuIdentity?.gpuName) || i18n.t('hardware.components.gpu')
            });
        }
        return devices;
    }

    #sync(): void {
        const devices = this.#resolveDevices();
        let devicesChanged = !this.#initialized || devices.size !== this.#devices.size;
        for (const [deviceId, device] of devices) {
            const previous = this.#devices.get(deviceId);
            if (!previous || previous.gpuName !== device.gpuName || previous.gpuIndex !== device.gpuIndex) devicesChanged = true;
        }
        const revisions = this.#resolveRevisions();
        for (const deviceId of this.#devices.keys()) {
            if (devices.has(deviceId)) continue;
            this.#entriesByDevice.delete(deviceId);
            this.#failedDevices.delete(deviceId);
            this.#loadingDevices.delete(deviceId);
            this.#revisionByDevice.delete(deviceId);
            this.#requestTokenByDevice.delete(deviceId);
        }
        this.#devices = devices;
        const changedDevices: SoAIBenchHistoryOpenRequest[] = [];
        for (const device of devices.values()) {
            const revision = revisions.get(device.deviceId) ?? '';
            if (this.#revisionByDevice.get(device.deviceId) === revision) continue;
            this.#revisionByDevice.set(device.deviceId, revision);
            changedDevices.push(device);
        }
        this.#initialized = true;
        if (devicesChanged) this.#scheduleRender();
        for (const device of changedDevices) this.#reloadDevice(device);
    }

    #resolveRevisions(): Map<string, string> {
        const runKeysByDevice = new Map<string, string[]>();
        for (const run of this.#streamRuns) {
            const runKeys = runKeysByDevice.get(run.deviceId) ?? [];
            runKeys.push(`${run.runId}:${run.status}`);
            runKeysByDevice.set(run.deviceId, runKeys);
        }
        return new Map([...runKeysByDevice].map(([deviceId, runKeys]) => [deviceId, runKeys.sort((left, right) => (left < right ? -1 : left > right ? 1 : 0)).join('|')]));
    }

    #reloadDevice(device: SoAIBenchHistoryOpenRequest): void {
        this.#loadingDevices.add(device.deviceId);
        this.#failedDevices.delete(device.deviceId);
        this.#scheduleRender();
        this.#startDeviceLoad(device);
    }

    #startDeviceLoad(device: SoAIBenchHistoryOpenRequest): void {
        const token = ++this.#requestSerial;
        this.#requestTokenByDevice.set(device.deviceId, token);
        void this.#loadDevice(device, token).catch((error) => {
            if (this.#requestTokenByDevice.get(device.deviceId) === token) this.#failDevice(device.deviceId, ensureError(error));
        });
    }

    async #loadDevice(device: SoAIBenchHistoryOpenRequest, token: number): Promise<void> {
        for (let attempt = 0; attempt < 2; attempt += 1) {
            let result: { response: JsonValue } | { error: Error };
            try {
                result = { response: await requestWebSocketSnapshotRecord('hardware.gpu.soaibench.history', serializeGpuSoAIBenchHistoryRequest(device.deviceId, HISTORY_LIMIT)) };
            } catch (error) {
                result = { error: ensureError(error) };
            }
            if (this.#requestTokenByDevice.get(device.deviceId) !== token) return;
            if ('error' in result) {
                if (attempt === 0) {
                    await sleepMs(READ_RETRY_DELAY_MS);
                    if (this.#requestTokenByDevice.get(device.deviceId) !== token) return;
                    continue;
                }
                this.#failDevice(device.deviceId, result.error);
                return;
            }
            try {
                const entries = normalizeHistoryRuns(decodeGpuOperationResponse(result.response)).map((run) => ({ request: device, run }));
                this.#entriesByDevice.set(device.deviceId, entries);
                this.#loadingDevices.delete(device.deviceId);
                this.#failedDevices.delete(device.deviceId);
                this.#scheduleRender();
            } catch (error) {
                this.#failDevice(device.deviceId, ensureError(error));
            }
            return;
        }
    }

    #failDevice(deviceId: string, error: Error): void {
        this.#entriesByDevice.delete(deviceId);
        this.#loadingDevices.delete(deviceId);
        this.#failedDevices.add(deviceId);
        errorHandler.error('SoAIBenchHistoryPagePanel', `Failed to load SoAIBench history for ${deviceId}`, error);
        this.#scheduleRender();
    }

    #render(): void {
        if (!(dom.resolve('#hardware-soaibench-history-panel') instanceof HTMLElement)) return;
        const entries = [...this.#entriesByDevice.values()].flatMap((deviceEntries) => deviceEntries);
        const byRun = new Map(entries.map((entry) => [entry.run, entry]));
        const sortedEntries = sortHistoryRuns(
            entries.map((entry) => entry.run),
            this.#sortState
        ).map((run) => {
            const entry = byRun.get(run);
            if (!entry) throw new Error('SoAIBench history entry missing');
            const request = this.#devices.get(entry.request.deviceId) ?? entry.request;
            return { request, run };
        });
        const stateText = this.#failedDevices.size ? i18n.t('hardware.modals.soaibenchHistory.pageLoadFailed') : this.#loadingDevices.size && !entries.length ? i18n.t('hardware.modals.soaibenchHistory.loading') : !entries.length ? i18n.t('hardware.modals.soaibenchHistory.pageEmpty') : null;
        renderPageHistoryTable(this.#host, sortedEntries, this.#sortState, stateText, this.#busyRunIds);
    }
}

export { SoAIBenchHistoryPagePanel };
