/* SoAI - Shared frontend connection status runtime [frontend/assets/ts/core/connectionstatus/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import type { HoldOptions } from '@core/connectionstatus/contracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';

interface ConnectionStatusRuntime {
    retainConnection: (label?: string, options?: HoldOptions) => symbol;
    releaseConnection: (token: symbol, context?: { reason?: string }) => boolean;
}

const isConnectionStatusRuntime = (value: ConnectionStatusRuntime | JsonValue | null | undefined): value is ConnectionStatusRuntime => {
    if (!isObject(value)) {
        return false;
    }
    return 'retainConnection' in value && isFunction(value.retainConnection) && 'releaseConnection' in value && isFunction(value.releaseConnection);
};

const requireConnectionStatusRuntime = (): ConnectionStatusRuntime => {
    const candidate = resolveKernelService('core.connectionStatus');
    if (!isConnectionStatusRuntime(candidate)) throw new Error('core.connectionStatus is not registered');
    return candidate;
};

const getConnectionStatusRuntime = (): ConnectionStatusRuntime | null => {
    const candidate = resolveOptionalKernelService('core.connectionStatus');
    return isConnectionStatusRuntime(candidate) ? candidate : null;
};

export { getConnectionStatusRuntime, requireConnectionStatusRuntime };
export type { ConnectionStatusRuntime };
