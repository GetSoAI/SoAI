/* SoAI - Shared frontend WebSocket client latency probe [frontend/assets/ts/core/websocketclient/latencyProbe.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { monotonicMs } from '@core/time/clock.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { telemetry } from '@core/telemetry/service.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import { WEBSOCKET_LATENCY_METRIC_NAME, WEBSOCKET_LATENCY_METRIC_SOURCE, WEBSOCKET_LATENCY_PROBE_INTERVAL_MS, WEBSOCKET_LATENCY_PROBE_TIMEOUT_MS } from '@core/websocketclient/constants.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';

interface WebSocketLatencyProbeHost {
    isConnected: () => boolean;
    sendPayload: (payload: JsonObject) => boolean;
}

interface PendingLatencyProbe {
    probeId: string;
    generation: number;
    startedAtMs: number;
}

class WebSocketLatencyProbe {
    #host: WebSocketLatencyProbeHost;
    #probeTimer: ReturnType<typeof setTimeout> | null = null;
    #timeoutTimer: ReturnType<typeof setTimeout> | null = null;
    #pendingProbe: PendingLatencyProbe | null = null;
    #generation = 0;
    #sequence = 0;
    #active = false;

    constructor(host: WebSocketLatencyProbeHost) {
        this.#host = host;
    }

    start(): void {
        this.#generation += 1;
        this.#active = true;
        this.#clearTimers();
        this.#pendingProbe = null;
        this.#publishLatency(null);
        this.#sendProbe();
    }

    stop(): void {
        this.#generation += 1;
        this.#active = false;
        this.#clearTimers();
        this.#pendingProbe = null;
        this.#publishLatency(null);
    }

    handleResult(payload: JsonValue): void {
        if (!this.#active || !isJsonObject(payload)) {
            return;
        }
        const probeIdValue = payload['probe_id'];
        if (!isString(probeIdValue)) {
            return;
        }
        const probeId = probeIdValue.trim();
        const pendingProbe = this.#pendingProbe;
        if (!pendingProbe || probeId !== pendingProbe.probeId || pendingProbe.generation !== this.#generation) {
            return;
        }
        this.#pendingProbe = null;
        this.#clearTimeoutTimer();
        this.#publishLatency(Math.max(0, Math.round(monotonicMs() - pendingProbe.startedAtMs)));
        this.#scheduleProbe(WEBSOCKET_LATENCY_PROBE_INTERVAL_MS);
    }

    #sendProbe(): void {
        if (!this.#active || this.#pendingProbe !== null) {
            return;
        }
        if (!this.#host.isConnected()) {
            this.#publishLatency(null);
            this.#scheduleProbe(WEBSOCKET_LATENCY_PROBE_INTERVAL_MS);
            return;
        }
        const generation = this.#generation;
        this.#sequence += 1;
        const probeId = `${generation}:${this.#sequence}`;
        this.#pendingProbe = {
            probeId,
            generation,
            startedAtMs: monotonicMs()
        };
        const sent = this.#sendPayload(probeId);
        if (!sent) {
            this.#pendingProbe = null;
            this.#publishLatency(null);
            this.#scheduleProbe(WEBSOCKET_LATENCY_PROBE_INTERVAL_MS);
            return;
        }
        this.#timeoutTimer = setTimeout(() => {
            const pendingProbe = this.#pendingProbe;
            if (!pendingProbe || pendingProbe.generation !== generation || pendingProbe.probeId !== probeId) {
                return;
            }
            this.#pendingProbe = null;
            this.#timeoutTimer = null;
            this.#publishLatency(null);
            this.#scheduleProbe(0);
        }, WEBSOCKET_LATENCY_PROBE_TIMEOUT_MS);
    }

    #scheduleProbe(delayMs: number): void {
        this.#clearProbeTimer();
        if (!this.#active) {
            return;
        }
        this.#probeTimer = setTimeout(() => {
            this.#probeTimer = null;
            this.#sendProbe();
        }, delayMs);
    }

    #sendPayload(probeId: string): boolean {
        try {
            return this.#host.sendPayload({
                type: WEBSOCKET_MESSAGE_TYPES.LATENCY_PROBE,
                'probe_id': probeId
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('WebSocketClient', 'Failed to send latency probe', runtimeError);
            return false;
        }
    }

    #publishLatency(latencyMs: number | null): void {
        telemetry.publishMetric(WEBSOCKET_LATENCY_METRIC_NAME, latencyMs, { source: WEBSOCKET_LATENCY_METRIC_SOURCE });
    }

    #clearTimers(): void {
        this.#clearProbeTimer();
        this.#clearTimeoutTimer();
    }

    #clearProbeTimer(): void {
        if (this.#probeTimer === null) {
            return;
        }
        clearTimeout(this.#probeTimer);
        this.#probeTimer = null;
    }

    #clearTimeoutTimer(): void {
        if (this.#timeoutTimer === null) {
            return;
        }
        clearTimeout(this.#timeoutTimer);
        this.#timeoutTimer = null;
    }
}

export { WebSocketLatencyProbe };
export type { WebSocketLatencyProbeHost };
