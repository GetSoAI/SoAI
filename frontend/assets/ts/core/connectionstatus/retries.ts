/* SoAI - Shared frontend connection status retries [frontend/assets/ts/core/connectionstatus/retries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const INITIAL_RESTART_DELAY_MS = 500;
const MAX_RESTART_DELAY_MS = 10000;

const normalizeDelayMs = (delayMs: number | null | undefined): number => {
    if (typeof delayMs !== 'number' || !Number.isFinite(delayMs) || delayMs <= 0) {
        return INITIAL_RESTART_DELAY_MS;
    }
    return delayMs;
};

const nextDelayMs = (delayMs: number): number => Math.min(normalizeDelayMs(delayMs) * 2, MAX_RESTART_DELAY_MS);

export { INITIAL_RESTART_DELAY_MS, MAX_RESTART_DELAY_MS, normalizeDelayMs, nextDelayMs };
