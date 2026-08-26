/* SoAI - Adaptive activity duration ticker scheduling state [frontend/assets/ts/pages/chat/controllers/page/durations/ActivityDurationTickerState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type DriftSample = {
    measuredAtMs: number;
    driftMs: number;
};

const SUB_MINUTE_INTERVAL_LADDER_MS: readonly number[] = [250, 500, 1_000];
const FASTEST_SUB_MINUTE_INTERVAL_MS = 250;
const DRIFT_SAMPLE_WINDOW_INTERVAL_COUNT = 8;
const ESCALATION_AVERAGE_DRIFT_RATIO = 0.4;
const ESCALATION_MISSED_CALLBACK_DRIFT_RATIO = 0.2;
const ESCALATION_MISSED_CALLBACK_COUNT = 3;
const RECOVERY_MAX_DRIFT_RATIO = 0.16;
const RECOVERY_SUSTAINED_HEALTHY_MS = 9_000;

class ActivityDurationTickerState {
    readonly #samples: DriftSample[] = [];
    #intervalMs = FASTEST_SUB_MINUTE_INTERVAL_MS;
    #healthyRecoveryStartedMs: number | null = null;

    get subMinuteIntervalMs(): number {
        return this.#intervalMs;
    }

    record(measuredAtMs: number, driftMs: number): void {
        const intervalMs = this.#intervalMs;
        this.#samples.push({ measuredAtMs, driftMs });
        const windowStartMs = measuredAtMs - intervalMs * DRIFT_SAMPLE_WINDOW_INTERVAL_COUNT;
        while ((this.#samples[0]?.measuredAtMs ?? measuredAtMs) < windowStartMs) {
            this.#samples.shift();
        }
        let totalDriftMs = 0;
        let missedCallbacks = 0;
        for (const sample of this.#samples) {
            totalDriftMs += sample.driftMs;
            if (sample.driftMs > intervalMs * ESCALATION_MISSED_CALLBACK_DRIFT_RATIO) {
                missedCallbacks += 1;
            }
        }
        const averageDriftMs = totalDriftMs / this.#samples.length;
        if (averageDriftMs > intervalMs * ESCALATION_AVERAGE_DRIFT_RATIO || missedCallbacks >= ESCALATION_MISSED_CALLBACK_COUNT) {
            this.#slowDown(intervalMs);
            return;
        }
        if (intervalMs === FASTEST_SUB_MINUTE_INTERVAL_MS) {
            return;
        }
        if (driftMs >= intervalMs * RECOVERY_MAX_DRIFT_RATIO) {
            this.#healthyRecoveryStartedMs = null;
            return;
        }
        this.#healthyRecoveryStartedMs ??= measuredAtMs;
        if (measuredAtMs - this.#healthyRecoveryStartedMs >= RECOVERY_SUSTAINED_HEALTHY_MS) {
            this.#speedUp(intervalMs);
        }
    }

    reset(): void {
        this.#samples.length = 0;
        this.#healthyRecoveryStartedMs = null;
        this.#intervalMs = FASTEST_SUB_MINUTE_INTERVAL_MS;
    }

    #slowDown(intervalMs: number): void {
        this.#healthyRecoveryStartedMs = null;
        this.#samples.length = 0;
        const slowerIntervalMs = SUB_MINUTE_INTERVAL_LADDER_MS.find((candidate) => candidate > intervalMs);
        if (slowerIntervalMs !== undefined) {
            this.#intervalMs = slowerIntervalMs;
        }
    }

    #speedUp(intervalMs: number): void {
        this.#healthyRecoveryStartedMs = null;
        this.#samples.length = 0;
        const fasterIntervalMs = SUB_MINUTE_INTERVAL_LADDER_MS.findLast((candidate) => candidate < intervalMs);
        if (fasterIntervalMs !== undefined) {
            this.#intervalMs = fasterIntervalMs;
        }
    }
}

export { ActivityDurationTickerState };
