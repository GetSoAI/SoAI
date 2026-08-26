/* SoAI - Chat feature stream rate tracker [frontend/assets/ts/features/chat/stream/ChatStreamRateTracker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const RATE_STALE_AFTER_MS = 2_000;
const RATE_SMOOTHING_TIME_CONSTANT_MS = 650;
const RATE_DECAY_TIME_CONSTANT_MS = 900;
const RATE_MIN_VISIBLE = 0.05;

class ChatStreamRateTracker {
    #lastUnits: number | null = null;
    #lastUnitsAtMs: number | null = null;
    #smoothedUnitsPerSecond: number | null = null;
    #smoothedUnitsPerSecondAtMs: number | null = null;

    reset(): void {
        this.#lastUnits = null;
        this.#lastUnitsAtMs = null;
        this.#smoothedUnitsPerSecond = null;
        this.#smoothedUnitsPerSecondAtMs = null;
    }

    applySample(totalUnits: number, nowMs: number): void {
        if (!Number.isFinite(totalUnits) || totalUnits < 0 || !Number.isFinite(nowMs)) {
            this.reset();
            return;
        }
        const normalizedUnits = Math.floor(totalUnits);
        const lastUnits = this.#lastUnits;
        const lastAtMs = this.#lastUnitsAtMs;
        if (lastUnits !== null && normalizedUnits < lastUnits) {
            this.#smoothedUnitsPerSecond = null;
            this.#smoothedUnitsPerSecondAtMs = null;
        }
        this.#lastUnits = normalizedUnits;
        this.#lastUnitsAtMs = nowMs;
        if (lastUnits === null || lastAtMs === null) {
            return;
        }
        const deltaUnits = normalizedUnits - lastUnits;
        const deltaMs = nowMs - lastAtMs;
        if (deltaUnits < 0 || deltaMs <= 0) {
            return;
        }
        const rate = (deltaUnits * 1000) / deltaMs;
        if (!Number.isFinite(rate) || rate < 0) {
            return;
        }
        const prior = this.#smoothedUnitsPerSecond;
        const priorAtMs = this.#smoothedUnitsPerSecondAtMs;
        if (prior === null || priorAtMs === null) {
            this.#smoothedUnitsPerSecond = rate;
            this.#smoothedUnitsPerSecondAtMs = nowMs;
            return;
        }
        const smoothingDeltaMs = nowMs - priorAtMs;
        const alpha = smoothingDeltaMs <= 0 ? 1 : 1 - Math.exp(-smoothingDeltaMs / RATE_SMOOTHING_TIME_CONSTANT_MS);
        this.#smoothedUnitsPerSecond = prior + alpha * (rate - prior);
        this.#smoothedUnitsPerSecondAtMs = nowMs;
    }

    resolveRate(nowMs: number): number {
        const rate = this.#smoothedUnitsPerSecond;
        const rateAtMs = this.#smoothedUnitsPerSecondAtMs;
        if (rate === null || rateAtMs === null || !Number.isFinite(nowMs)) {
            return 0;
        }
        const ageMs = nowMs - rateAtMs;
        if (ageMs <= RATE_STALE_AFTER_MS) {
            return rate;
        }
        const decayMs = ageMs - RATE_STALE_AFTER_MS;
        const decayed = rate * Math.exp(-decayMs / RATE_DECAY_TIME_CONSTANT_MS);
        if (!Number.isFinite(decayed) || decayed < RATE_MIN_VISIBLE) {
            return 0;
        }
        return decayed;
    }
}

export { ChatStreamRateTracker };
