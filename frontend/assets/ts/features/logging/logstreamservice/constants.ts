/* SoAI - Logging feature log stream service constants [frontend/assets/ts/features/logging/logstreamservice/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LOGS_CORE } from '@core/realtime/streammanager/resources/ids.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isString } from '@core/typeGuards.ts';

const MODULE_ID = 'features.logging.logStreamService';
const LOG_STREAM_SERVICE_ID = 'features.logging.logStreamService';

const DEFAULT_REPLAY_LIMIT = 500;
const MAX_BUFFER_SIZE = 5000;
const RECONNECT_NOTICE_DELAY_MS = 750;
const SHARED_BUFFER_SYNC_DELAY_MS = 64;

const LOG_BUNDLE_STATE_KEY = 'stream.bundle.logs';
const LOG_RESOURCE_NAME = LOGS_CORE;

const getNow = (): number => {
    const performanceApi = globalThis?.performance;
    if (Boolean(performanceApi) && isFunction(performanceApi?.now)) {
        return performanceApi.now();
    }
    return Date.now();
};

const cleanStr = (value: JsonValue | null | undefined): string | null => {
    return toTrimmedStringOrNull(value);
};

const resolveDefaultLogSource = (): string => {
    if (isString(LOG_RESOURCE_NAME)) {
        const segments = LOG_RESOURCE_NAME.split('.');
        const lastSegment = segments[segments.length - 1];
        if (lastSegment && lastSegment.trim()) {
            return lastSegment.trim();
        }
    }

    return 'core';
};

const DEFAULT_LOG_SOURCE = resolveDefaultLogSource();
const CORE_LOG_SOURCE = DEFAULT_LOG_SOURCE;

export { CORE_LOG_SOURCE, DEFAULT_LOG_SOURCE, DEFAULT_REPLAY_LIMIT, getNow, LOG_BUNDLE_STATE_KEY, LOG_RESOURCE_NAME, LOG_STREAM_SERVICE_ID, MAX_BUFFER_SIZE, MODULE_ID, RECONNECT_NOTICE_DELAY_MS, SHARED_BUFFER_SYNC_DELAY_MS, cleanStr };
