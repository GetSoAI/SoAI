/* SoAI - Metrics feature snapshot [frontend/assets/ts/features/metrics/metricsSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

interface TokenRateMetrics {
    effectiveRate?: number;
    deliveredRate5s?: number;
    deliveredRate30s?: number;
    activeStreams?: number;
}

interface Metrics {
    tokenRates?: {
        total?: TokenRateMetrics;
        plugins?: Record<string, TokenRateMetrics>;
    };
    billing?: {
        totalTokensGenerated?: number;
    };
    genesis?: {
        requestsTotal?: number;
        tokensTotal?: number;
        uptimeMs?: number;
    };
    director?: {
        gauges?: {
            queueSize?: number;
            requestLatencyMs?: number;
            pluginHealth?: JsonObject;
            pendingLoads?: number;
            pluginConcurrencyActive?: JsonObject;
        };
        modelLoads?: {
            successful?: number;
            failed?: number;
        };
        requests?: {
            total?: number;
            failed?: number;
            completed?: number;
            deduplicated?: number;
            fastPath?: number;
        };
    };
    database?: {
        gauges?: {
            writeQueueDepth?: number;
        };
    };
    eventBus?: {
        eventsDropped?: number;
        gauges?: {
            queueDepth?: number;
        };
    };
    streaming?: {
        backpressure?: {
            droppedEvents?: number;
        };
        delivery?: {
            timeoutCount?: number;
        };
    };
    modelManager?: {
        discoveriesRun?: number;
        modelsUpdated?: number;
    };
}

export type { Metrics, TokenRateMetrics };
