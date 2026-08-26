/* SoAI - Shared frontend WebSocket client constants [frontend/assets/ts/core/websocketclient/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { WEBSOCKET } from '@core/constants.ts';
import type { TimerState } from '@core/websocketclient/types.ts';

const { ENDPOINT, RECONNECT_DELAY_INITIAL_MS, RECONNECT_DELAY_MAX_MS, RECONNECT_STABILITY_MS, HEARTBEAT_TIMEOUT_MS, CONNECTION_TIMEOUT_MS } = WEBSOCKET;

const CONNECTION_STATES = Object.freeze({
    DISCONNECTED: 'disconnected',
    CONNECTING: 'connecting',
    CONNECTED: 'connected',
    RECONNECTING: 'reconnecting'
});

const SNAPSHOT_TIMEOUT_MS = 30000;
const SNAPSHOT_TIMEOUT_MESSAGE_PREFIX = 'Snapshot request timeout:';
const PERMANENT_SHUTDOWN_REASONS = new Set<string>(['system-shutdown']);
const TIMER_KEYS = ['heartbeat', 'connectionTimeout', 'reconnectStability'] satisfies ReadonlyArray<keyof TimerState>;
const WEBSOCKET_PROTOCOL_VERSION = 1;
const WEBSOCKET_LATENCY_METRIC_NAME = 'connection.latencyMs';
const WEBSOCKET_LATENCY_METRIC_SOURCE = 'websocket';
const WEBSOCKET_LATENCY_PROBE_INTERVAL_MS = 5000;
const WEBSOCKET_LATENCY_PROBE_TIMEOUT_MS = 15000;

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

export { ENDPOINT, RECONNECT_DELAY_INITIAL_MS, RECONNECT_DELAY_MAX_MS, RECONNECT_STABILITY_MS, HEARTBEAT_TIMEOUT_MS, CONNECTION_TIMEOUT_MS, SNAPSHOT_TIMEOUT_MS, SNAPSHOT_TIMEOUT_MESSAGE_PREFIX, PERMANENT_SHUTDOWN_REASONS, CONNECTION_STATES, TIMER_KEYS, WEBSOCKET_PROTOCOL_VERSION, WEBSOCKET_LATENCY_METRIC_NAME, WEBSOCKET_LATENCY_METRIC_SOURCE, WEBSOCKET_LATENCY_PROBE_INTERVAL_MS, WEBSOCKET_LATENCY_PROBE_TIMEOUT_MS };
export type { ConnectionState };
