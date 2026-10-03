/* SoAI - Charts feature history session [frontend/assets/ts/features/charts/historySession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { HistoryRequestFence, type HistoryRequestLease } from '@features/charts/historyRequestFence.ts';

const MAX_BUFFERED_REALTIME_SAMPLES = 4096;

class HistorySession<RealtimeSample = never> {
    readonly request = new HistoryRequestFence();
    initialized = false;
    #probe: Promise<void> | null = null;
    #latestRealtimeSampleMs: number | null = null;
    #realtimeCapture: RealtimeSample[] | null = null;
    #realtimeCaptureOverflowed = false;

    invalidate(): void {
        this.request.invalidate();
        this.initialized = false;
        this.#latestRealtimeSampleMs = null;
        this.stopRealtimeCapture();
    }

    beginRealtimeCapture(): void {
        this.#realtimeCapture = [];
        this.#realtimeCaptureOverflowed = false;
    }

    captureRealtimeSample(sample: RealtimeSample): void {
        if (!this.#realtimeCapture || this.#realtimeCaptureOverflowed) return;
        if (this.#realtimeCapture.length >= MAX_BUFFERED_REALTIME_SAMPLES) {
            this.#realtimeCapture = [];
            this.#realtimeCaptureOverflowed = true;
            return;
        }
        this.#realtimeCapture.push(sample);
    }

    replayRealtimeSamples(apply: (sample: RealtimeSample) => void): void {
        const samples = this.#realtimeCapture ?? [];
        const overflowed = this.#realtimeCaptureOverflowed;
        this.stopRealtimeCapture();
        if (overflowed) throw new Error('Realtime history capture exceeded its bounded capacity');
        for (const sample of samples) apply(sample);
    }

    stopRealtimeCapture(): void {
        this.#realtimeCapture = null;
        this.#realtimeCaptureOverflowed = false;
    }

    releaseRealtimeCapture(lease: HistoryRequestLease): void {
        if (this.request.isCurrent(lease)) this.stopRealtimeCapture();
    }

    setRealtimeBoundary(timestamp: number | null, historyEndMs: number): void {
        if ((timestamp !== null && !Number.isFinite(timestamp)) || !Number.isFinite(historyEndMs)) throw new TypeError('Realtime boundary must be finite');
        this.#latestRealtimeSampleMs = timestamp === null ? null : Math.min(timestamp, historyEndMs);
    }

    acceptRealtimeTimestamp(timestamp: number): boolean {
        if (!Number.isFinite(timestamp) || (this.#latestRealtimeSampleMs !== null && timestamp <= this.#latestRealtimeSampleMs)) return false;
        this.#latestRealtimeSampleMs = timestamp;
        return true;
    }

    probeOnce(task: () => Promise<void>, onError: (error: Error) => void): void {
        if (this.#probe) return;
        const probe = task()
            .catch((error) => onError(ensureError(error)))
            .finally(() => {
                if (this.#probe === probe) this.#probe = null;
            });
        this.#probe = probe;
    }
}

export { HistorySession };
