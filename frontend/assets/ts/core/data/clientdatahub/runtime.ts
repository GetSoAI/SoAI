/* SoAI - Client data hub service ownership [frontend/assets/ts/core/data/clientdatahub/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ClientDataHub } from '@core/data/ClientDataHub.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

const CLIENT_DATA_HUB_SERVICE_ID = 'core.clientDataHub';

const requireClientDataHub = (): ClientDataHub => {
    const service = resolveKernelService(CLIENT_DATA_HUB_SERVICE_ID);
    if (!(service instanceof ClientDataHub)) throw new Error(`${CLIENT_DATA_HUB_SERVICE_ID} must expose ClientDataHub`);
    return service;
};

export { CLIENT_DATA_HUB_SERVICE_ID, requireClientDataHub };
