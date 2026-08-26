/* SoAI - Frontend connection status service registry [frontend/assets/ts/core/connectionstatus/connectionStatusRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ConnectionStatus } from '@core/connectionstatus/service.ts';
import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';

export type { ConnectionEvent, RestartInfo, SystemInfo, StatusSnapshot, StatusSubscriber, RestartSubscriber } from '@core/connectionstatus/types.ts';

const CONNECTION_STATUS_SERVICE_ID = 'core.connectionStatus';

const createConnectionStatus = (): ConnectionStatus => new ConnectionStatus();

const getConnectionStatus = (): ConnectionStatus | null => {
    const candidate = resolveOptionalKernelService(CONNECTION_STATUS_SERVICE_ID);
    return candidate instanceof ConnectionStatus ? candidate : null;
};

const requireConnectionStatus = (): ConnectionStatus => {
    const candidate = resolveKernelService(CONNECTION_STATUS_SERVICE_ID);
    if (!(candidate instanceof ConnectionStatus)) {
        throw new Error(`${CONNECTION_STATUS_SERVICE_ID} is not registered`);
    }
    return candidate;
};

export { ConnectionStatus, createConnectionStatus, getConnectionStatus, requireConnectionStatus, CONNECTION_STATUS_SERVICE_ID };
