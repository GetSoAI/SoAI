/* SoAI - Shared realtime readiness [frontend/assets/ts/core/realtime/streammanager/readiness.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { withTimeout } from '@core/primitives/withTimeout.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface StreamManagerReadinessTarget {
    ensureReady: (options: { allowDiscovery: boolean; signal?: AbortSignal | undefined }) => Promise<void>;
    startAuto?: ((options?: { signal?: AbortSignal | undefined }) => Promise<JsonValue[] | null | undefined>) | undefined;
}

interface EnsureStreamManagerReadyOptions {
    allowDiscovery?: boolean | undefined;
    autoResources?: boolean | 'background' | undefined;
    signal?: AbortSignal | undefined;
}

const DATA_HUB_READY_TIMEOUT_MS = 10000;
const DATA_HUB_AUTO_RESOURCES_TIMEOUT_MS = 60000;

const ensureAutoResourcesReady = (manager: StreamManagerReadinessTarget): Promise<JsonValue | null | undefined> => {
    if (!manager.startAuto) {
        throw new Error('Stream manager auto-resource readiness API is not available');
    }
    return manager.startAuto();
};

const startAutoResourcesInBackground = (manager: StreamManagerReadinessTarget): void => {
    if (!manager.startAuto) {
        throw new Error('Stream manager auto-resource readiness API is not available');
    }
    void manager.startAuto().catch((error) => {
        errorHandler.warn('StreamManager', 'Background auto-resource initialization failed', ensureError(error));
    });
};

const ensureStreamManagerReady = async (manager: StreamManagerReadinessTarget, options: EnsureStreamManagerReadyOptions = {}): Promise<void> => {
    const allowDiscovery = options.allowDiscovery !== false;
    await withTimeout(manager.ensureReady({ allowDiscovery, signal: options.signal }), {
        timeoutMs: DATA_HUB_READY_TIMEOUT_MS,
        timeoutMessage: 'Stream manager ensureReady timeout'
    });
    if (options.autoResources === 'background') {
        startAutoResourcesInBackground(manager);
        return;
    }
    if (options.autoResources !== true) {
        return;
    }
    await withTimeout(ensureAutoResourcesReady(manager), {
        timeoutMs: DATA_HUB_AUTO_RESOURCES_TIMEOUT_MS,
        timeoutMessage: 'Stream manager ensureAutoResources timeout'
    });
};

export { ensureStreamManagerReady };
export type { EnsureStreamManagerReadyOptions, StreamManagerReadinessTarget };
