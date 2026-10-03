/* SoAI - SoAIBench per-run result export and publication actions [frontend/assets/ts/features/hardware/modals/soaibenchrun/resultActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DeferredButtonLoading } from '@core/ui/loadingbuttons/deferredLoadingButton.ts';
import { HARDWARE_SOAIBENCH_RUN_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_RUN_PUBLISH_ACTION } from '@features/hardware/modals/soaibenchrun/constants.ts';
import { copySoAIBenchRunExport, downloadSoAIBenchRunExport } from '@features/hardware/modals/soaibenchrun/exportActions.ts';
import { exportRunFromRunRecord } from '@features/hardware/modals/soaibenchrun/exportText.ts';
import type { SoAIBenchRunModalDependencies, SoAIBenchRunModalHost, SoAIBenchRunOpenRequest, SoAIBenchRunRecord } from '@features/hardware/modals/soaibenchrun/types.ts';

interface SoAIBenchResultTarget {
    request: SoAIBenchRunOpenRequest;
    run: SoAIBenchRunRecord;
}

type SoAIBenchResultTargetResolver = () => SoAIBenchResultTarget;

interface SoAIBenchResultActionDependencies {
    host: SoAIBenchRunModalHost;
    publishRun: SoAIBenchRunModalDependencies['publishRun'];
    resolveActionButton(runId: string, action: string): HTMLButtonElement | null;
    onPublicationChange(runId: string): void;
}

class SoAIBenchResultActions {
    readonly #dependencies: SoAIBenchResultActionDependencies;
    readonly #downloads = new Map<string, DeferredButtonLoading>();
    readonly #publications = new Map<string, DeferredButtonLoading>();
    #generation = 0;

    constructor(dependencies: SoAIBenchResultActionDependencies) {
        this.#dependencies = dependencies;
    }

    isPublishing(runId: string | null): boolean {
        return runId !== null && this.#publications.has(runId);
    }

    reset(): void {
        this.#generation += 1;
        for (const loading of [...this.#downloads.values(), ...this.#publications.values()]) {
            loading.settle();
        }
        this.#downloads.clear();
        this.#publications.clear();
    }

    copy(resolveTarget: SoAIBenchResultTargetResolver): Promise<void> {
        return this.#dependencies.host.runWithBoundary('hardware:copySoAIBenchRun', async () => {
            const target = resolveTarget();
            await copySoAIBenchRunExport({ host: this.#dependencies.host, request: target.request, run: exportRunFromRunRecord(target.run) });
        });
    }

    async download(runId: string, resolveTarget: SoAIBenchResultTargetResolver): Promise<void> {
        if (this.#downloads.has(runId)) {
            return;
        }
        const loading = new DeferredButtonLoading();
        const generation = this.#generation;
        this.#downloads.set(runId, loading);
        loading.begin(this.#dependencies.resolveActionButton(runId, HARDWARE_SOAIBENCH_RUN_DOWNLOAD_ACTION));
        try {
            await this.#dependencies.host.runWithBoundary('hardware:downloadSoAIBenchRun', async () => {
                const target = resolveTarget();
                downloadSoAIBenchRunExport({ host: this.#dependencies.host, request: target.request, run: exportRunFromRunRecord(target.run) });
            });
        } finally {
            loading.settle();
            if (generation === this.#generation && this.#downloads.get(runId) === loading) {
                this.#downloads.delete(runId);
            }
        }
    }

    async publish(runId: string, resolveTarget: SoAIBenchResultTargetResolver): Promise<void> {
        if (this.#publications.has(runId)) {
            return;
        }
        const loading = new DeferredButtonLoading();
        const generation = this.#generation;
        this.#publications.set(runId, loading);
        loading.begin(this.#dependencies.resolveActionButton(runId, HARDWARE_SOAIBENCH_RUN_PUBLISH_ACTION));
        this.#dependencies.onPublicationChange(runId);
        try {
            await this.#dependencies.host.runWithBoundary('hardware:publishSoAIBenchRun', async () => {
                const target = resolveTarget();
                await this.#dependencies.publishRun(target.run, (disabled) => {
                    if (!disabled) {
                        this.#finishPublication(runId, loading, generation);
                    }
                });
            });
        } finally {
            this.#finishPublication(runId, loading, generation);
        }
    }

    #finishPublication(runId: string, loading: DeferredButtonLoading, generation: number): void {
        loading.settle();
        if (generation !== this.#generation || this.#publications.get(runId) !== loading) {
            return;
        }
        this.#publications.delete(runId);
        this.#dependencies.onPublicationChange(runId);
    }
}

export { SoAIBenchResultActions };
export type { SoAIBenchResultTarget };
