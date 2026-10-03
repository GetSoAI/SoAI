/* SoAI - Core timeout, stream, HTTP, and WebSocket constants [frontend/assets/ts/core/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString } from '@core/assertions.ts';
import { hasOwn, isObject } from '@core/typeGuards.ts';

const PAGE_READINESS_TIMEOUT_MS = 180000;
const INITIAL_MODEL_COLLECTION_TIMEOUT_MS = 90000;

const TIMEOUTS = Object.freeze({
    CORE_MODULES: 120000,
    PAGE_LOAD: 60000,
    API_REQUEST: 90000,
    STREAM_CONNECT: INITIAL_MODEL_COLLECTION_TIMEOUT_MS,
    NOTIFICATION: 5000,
    DEBOUNCE: 300,
    THROTTLE: 100,
    ANIMATION: 300
});

const STREAMS = Object.freeze({
    MODELS_COLLECTION: 'models.collection',
    PLUGINS_COLLECTION: 'plugins.collection',
    MODELS_LAST_USED: 'models.last_used',
    PLUGINS_LAST_USED: 'plugins.last_used',
    PROMPTS_COLLECTION: 'prompts.collection',
    PROVIDERS_COLLECTION: 'providers.collection',
    HARDWARE_SNAPSHOT: 'hardware.snapshot',
    SYSTEM_STATUS: 'system.status',
    POWER_OPERATIONS: 'system.power.operations',
    SYSTEM_METRICS: 'system.metrics',
    SYSTEM_LOGS_CORE: 'system.logs.core',
    PLUGIN_CAPABILITIES_MANIFEST: 'plugins.capabilities.manifest',
    ROUTING_CONFIG: 'routing.config',
    VIRTUAL_MODELS: 'routing.virtualModels',
    WEBUI_NOTIFICATIONS: 'webui.notifications'
});

const HTTP = Object.freeze({
    DEFAULT_HEADERS: { 'Content-Type': 'application/json' }
});

const WEBSOCKET = Object.freeze({
    ENDPOINT: '/api/v1/system/ws',
    RECONNECT_DELAY_INITIAL_MS: 1000,
    RECONNECT_DELAY_MAX_MS: 30000,
    RECONNECT_STABILITY_MS: 10000,
    HEARTBEAT_TIMEOUT_MS: 90000,
    CONNECTION_TIMEOUT_MS: 90000
});

const constants = Object.freeze({
    HTTP,
    STREAMS,
    TIMEOUTS,
    WEBSOCKET
});

type StreamsConfig = typeof STREAMS;
type StreamKey = keyof typeof STREAMS;

const normalizeStreamKey = (key: string): string => assertNonEmptyString(key, 'Stream key');

const getStreamsConfig = (): StreamsConfig => {
    const streams = constants.STREAMS;
    if (!isObject(streams)) {
        throw new Error('Runtime constants must include STREAMS');
    }
    return streams;
};

const isStreamKey = (streams: StreamsConfig, key: string): key is StreamKey => {
    return hasOwn(streams, key);
};

function getStreamId<Key extends StreamKey>(key: Key): StreamsConfig[Key];
function getStreamId(key: string): string {
    const normalizedKey = normalizeStreamKey(key);
    const streams = getStreamsConfig();
    if (!isStreamKey(streams, normalizedKey)) {
        throw new Error(`Unknown stream key: ${normalizedKey}`);
    }
    const streamId = assertNonEmptyString(streams[normalizedKey], `STREAMS.${normalizedKey}`, {
        message: `STREAMS.${normalizedKey} must be a non-empty string`
    });
    return streamId;
}

export { constants, HTTP, INITIAL_MODEL_COLLECTION_TIMEOUT_MS, PAGE_READINESS_TIMEOUT_MS, STREAMS, TIMEOUTS, WEBSOCKET, getStreamsConfig, getStreamId };

export type { StreamsConfig, StreamKey };
