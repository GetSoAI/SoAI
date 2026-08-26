/* SoAI - Shared frontend connection status constants [frontend/assets/ts/core/connectionstatus/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { INITIAL_RESTART_DELAY_MS } from '@core/connectionstatus/retries.ts';

const MODULE_NAME = 'ConnectionStatus';
const SRC = 'core.connectionStatus';
const EVT_UPDATE = 'update';
const EVT_DISCO = 'disconnected';
const DEFAULT_INITIAL_SNAPSHOT_TIMEOUT_MS = 10000;
const DISCONNECT_EVAL_DELAY_MS = 500;
const CONNECTED_EVENT_THROTTLE_MS = 500;
const METRIC_STAT = 'connection.status';
const METRIC_QD = 'stream.queueDepth';
const REASON_MAIN = 'maintenance';
const STREAM_TELEMETRY_STAGE_CONNECTED = 'connection:connected';
const STREAM_TELEMETRY_STAGE_LOST = 'connection:lost';
const STREAM_METRIC_STAGE_CONNECTED = 'connection:connected';
const STREAM_METRIC_STAGE_LOST = 'connection:lost';

const STATEFUL_STATUS_EVENTS: ReadonlySet<string> = new Set([EVT_UPDATE, 'initial', 'fetch', 'immediate', 'connected']);

type TelemetrySeverity = 'debug' | 'info' | 'warn' | 'error';

interface TelemetryOptions {
    duration?: number | null;
    queueDepth?: number | null;
    attempt?: number;
    maxAttempts?: number;
}

export { MODULE_NAME, SRC, EVT_DISCO, EVT_UPDATE, DEFAULT_INITIAL_SNAPSHOT_TIMEOUT_MS, DISCONNECT_EVAL_DELAY_MS, CONNECTED_EVENT_THROTTLE_MS, INITIAL_RESTART_DELAY_MS, METRIC_STAT, METRIC_QD, REASON_MAIN, STATEFUL_STATUS_EVENTS, STREAM_TELEMETRY_STAGE_CONNECTED, STREAM_TELEMETRY_STAGE_LOST, STREAM_METRIC_STAGE_CONNECTED, STREAM_METRIC_STAGE_LOST };

export type { TelemetryOptions, TelemetrySeverity };
