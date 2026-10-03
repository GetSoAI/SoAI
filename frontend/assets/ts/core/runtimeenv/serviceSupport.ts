/* SoAI - Shared runtime environment service support [frontend/assets/ts/core/runtimeenv/serviceSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { getLocation } from '@core/environment/public.ts';
import { isString } from '@core/typeGuards.ts';
import { MAX_HOST_ID_LENGTH, SYSTEM_LOGS_CORE_STREAM, VALID_HOST_ID_PATTERN } from '@core/runtimeenv/constants.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';

interface RuntimeEnvLogger {
    logDetachedWarning: (message: string, details?: TelemetryValue) => void;
}
const LOG_TAG_DETACHED = 'DetachedCoordinator';
let hostWindowIdCache: string | null = null;
const resolveHostWindowId = (): string => {
    if (!windowIdentity.isDetachedContext()) {
        return windowIdentity.current();
    }
    const search = getLocation().search;
    if (!isString(search)) {
        throw new Error('Detached windows require search parameters');
    }
    const hostId = new URLSearchParams(search).get('hostId');
    if (!hostId || !hostId.trim()) {
        throw new Error('Detached windows must include hostId query parameter');
    }
    const trimmedHostId = hostId.trim();
    if (trimmedHostId.length > MAX_HOST_ID_LENGTH) {
        throw new Error('hostId exceeds maximum length');
    }
    if (!VALID_HOST_ID_PATTERN.test(trimmedHostId)) {
        throw new Error('hostId contains invalid characters');
    }
    return trimmedHostId;
};
const getHostWindowId = (): string => (hostWindowIdCache ??= resolveHostWindowId());

export { LOG_TAG_DETACHED, getHostWindowId, SYSTEM_LOGS_CORE_STREAM };
export type { RuntimeEnvLogger };
