/* SoAI - Shared realtime runtime [frontend/assets/ts/core/realtime/streammanager/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import type { StreamManager } from '@core/realtime/streammanager/StreamManager.ts';

const STREAM_MANAGER_SERVICE_ID = 'core.streamLifecycle';

interface StreamManagerCandidate {
    reset?: WeakKey | null;
    resetAllResourceRuntimeState?: WeakKey | null;
    dispose?: WeakKey | null;
    attachConnectionStatus?: WeakKey | null;
    resources?: WeakKey | null;
    subscriptions?: WeakKey | null;
    tasks?: WeakKey | null;
    connection?: WeakKey | null;
}

const isStreamManager = (value: StreamManagerCandidate | null | undefined): value is StreamManager => {
    if (!isObject(value)) {
        return false;
    }
    const requiredMethods: readonly string[] = ['reset', 'resetAllResourceRuntimeState', 'dispose', 'attachConnectionStatus'];
    if (!requiredMethods.every((method) => hasFunctionProperty(value, method))) return false;
    return isObject(value['resources']) && isObject(value['subscriptions']) && isObject(value['tasks']) && isObject(value['connection']);
};

const requireStreamManager = (): StreamManager => {
    const candidate = resolveKernelService(STREAM_MANAGER_SERVICE_ID);
    if (!isStreamManager(candidate)) {
        throw new Error(`${STREAM_MANAGER_SERVICE_ID} is not registered`);
    }
    return candidate;
};

const getStreamManager = (): StreamManager | null => {
    const candidate = resolveOptionalKernelService(STREAM_MANAGER_SERVICE_ID);
    if (!isStreamManager(candidate)) {
        return null;
    }
    return candidate;
};

export { getStreamManager, requireStreamManager };
export type { StreamManagerCandidate };
