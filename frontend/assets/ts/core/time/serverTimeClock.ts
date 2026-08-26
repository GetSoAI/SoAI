/* SoAI - Authoritative server epoch projected by the browser monotonic clock [frontend/assets/ts/core/time/serverTimeClock.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requirePerformanceNow } from '@core/environment/public.ts';

const SOAI_SERVER_TIME_HEADER_NAME = 'X-SoAI-Server-Time-Ms';
const MAX_SERVER_TIMESTAMP_MS = 0xffffffffffff;

type MonotonicClock = () => number;
type ServerTimeResponseTiming = {
    requestStartedAtMonotonicMs: number;
    responseReceivedAtMonotonicMs: number;
};
class ServerTimeClock {
    readonly #monotonicNow: MonotonicClock;
    #serverTimeAnchorMs: number | null = null;
    #anchorObservedAtMs = 0;
    #lastResolvedServerTimeMs: number | null = null;
    #responseUncertaintyMs: number | null = null;

    constructor(monotonicNow: MonotonicClock) {
        this.#monotonicNow = monotonicNow;
    }

    observe(serverTimeMs: number): void {
        this.#requireTimestamp(serverTimeMs);
        const monotonicNowMs = this.#requireMonotonicNow();
        const projectedTimeMs = this.#serverTimeAnchorMs === null ? serverTimeMs : this.#serverTimeAnchorMs + Math.max(0, monotonicNowMs - this.#anchorObservedAtMs);
        this.#serverTimeAnchorMs = Math.max(serverTimeMs, projectedTimeMs);
        this.#anchorObservedAtMs = monotonicNowMs;
        this.#responseUncertaintyMs = null;
    }

    reanchor(serverTimeMs: number): void {
        this.#requireTimestamp(serverTimeMs);
        this.#serverTimeAnchorMs = serverTimeMs;
        this.#anchorObservedAtMs = this.#requireMonotonicNow();
        this.#lastResolvedServerTimeMs = serverTimeMs;
        this.#responseUncertaintyMs = null;
    }

    observeResponse(serverTimeMs: number, timing: ServerTimeResponseTiming): void {
        this.#requireTimestamp(serverTimeMs);
        const requestStartedAtMonotonicMs = this.#requireMonotonicValue(timing.requestStartedAtMonotonicMs);
        const responseReceivedAtMonotonicMs = this.#requireMonotonicValue(timing.responseReceivedAtMonotonicMs);
        if (responseReceivedAtMonotonicMs < requestStartedAtMonotonicMs) {
            throw new Error('Authoritative server time response timing is invalid');
        }
        if (this.#serverTimeAnchorMs !== null && requestStartedAtMonotonicMs < this.#anchorObservedAtMs) {
            return;
        }
        const roundTripMs = responseReceivedAtMonotonicMs - requestStartedAtMonotonicMs;
        const maximumServerTimeAtReceiptMs = Math.floor(serverTimeMs + roundTripMs);
        this.#requireTimestamp(maximumServerTimeAtReceiptMs);
        const projectedTimeMs = this.#serverTimeAnchorMs === null ? null : Math.floor(this.#serverTimeAnchorMs + Math.max(0, responseReceivedAtMonotonicMs - this.#anchorObservedAtMs));
        if (projectedTimeMs === null || projectedTimeMs < serverTimeMs || projectedTimeMs > maximumServerTimeAtReceiptMs) {
            this.#serverTimeAnchorMs = serverTimeMs;
            if (projectedTimeMs !== null && projectedTimeMs > maximumServerTimeAtReceiptMs) {
                this.#lastResolvedServerTimeMs = serverTimeMs;
            }
        } else {
            this.#serverTimeAnchorMs = projectedTimeMs;
        }
        this.#anchorObservedAtMs = responseReceivedAtMonotonicMs;
        this.#responseUncertaintyMs = roundTripMs;
    }

    uncertaintyMs(): number | null {
        return this.#responseUncertaintyMs;
    }

    now(): number {
        if (this.#serverTimeAnchorMs === null) {
            throw new Error('Authoritative server time is unavailable');
        }
        const projectedTimeMs = Math.floor(this.#serverTimeAnchorMs + Math.max(0, this.#requireMonotonicNow() - this.#anchorObservedAtMs));
        const resolvedTimeMs = Math.max(projectedTimeMs, this.#lastResolvedServerTimeMs ?? 0);
        this.#requireTimestamp(resolvedTimeMs);
        this.#lastResolvedServerTimeMs = resolvedTimeMs;
        return resolvedTimeMs;
    }

    #requireTimestamp(value: number): void {
        if (!Number.isSafeInteger(value) || value < 0 || value > MAX_SERVER_TIMESTAMP_MS) {
            throw new Error('Authoritative server time requires a valid epoch timestamp');
        }
    }

    #requireMonotonicNow(): number {
        return this.#requireMonotonicValue(this.#monotonicNow());
    }

    #requireMonotonicValue(value: number): number {
        if (!Number.isFinite(value) || value < 0) {
            throw new Error('Authoritative server time monotonic clock returned an invalid value');
        }
        return value;
    }
}

let authoritativeServerTimeClock: ServerTimeClock | null = null;

const initializeServerTimeClock = (): void => {
    authoritativeServerTimeClock ??= new ServerTimeClock(requirePerformanceNow());
};

const requireServerTimeClock = (): ServerTimeClock => {
    if (!authoritativeServerTimeClock) {
        throw new Error('Authoritative server time clock is not initialized');
    }
    return authoritativeServerTimeClock;
};

const observeServerTime = (serverTimeMs: number): void => requireServerTimeClock().observe(serverTimeMs);
const reanchorServerTime = (serverTimeMs: number): void => requireServerTimeClock().reanchor(serverTimeMs);
const resolveServerTimeMs = (): number => requireServerTimeClock().now();
const resolveServerTimeUncertaintyMs = (): number | null => requireServerTimeClock().uncertaintyMs();

const observeServerTimeResponse = (response: Response, timing: ServerTimeResponseTiming): void => {
    const headerValue = response.headers.get(SOAI_SERVER_TIME_HEADER_NAME);
    if (headerValue === null) throw new Error('SoAI server-time response header is missing');
    if (!/^\d+$/.test(headerValue)) throw new Error('SoAI server-time response header is invalid');
    const serverTimeMs = Number(headerValue);
    if (!Number.isSafeInteger(serverTimeMs)) throw new Error('SoAI server-time response header is invalid');
    requireServerTimeClock().observeResponse(serverTimeMs, timing);
};

export { initializeServerTimeClock, observeServerTime, observeServerTimeResponse, reanchorServerTime, resolveServerTimeMs, resolveServerTimeUncertaintyMs, ServerTimeClock, SOAI_SERVER_TIME_HEADER_NAME };
export type { MonotonicClock, ServerTimeResponseTiming };
