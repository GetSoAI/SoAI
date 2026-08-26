/* SoAI - Shared routing router runtime [frontend/assets/ts/core/routing/router/routerRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { Router } from '@core/routing/router/Router.ts';
import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';

const ROUTER_SERVICE_ID = 'core.router';

const getRouterOptional = (): Router | null => {
    const candidate = resolveOptionalKernelService(ROUTER_SERVICE_ID);
    return candidate instanceof Router ? candidate : null;
};

const requireRouter = (): Router => {
    const candidate = resolveKernelService(ROUTER_SERVICE_ID);
    if (!(candidate instanceof Router)) {
        throw new Error(`${ROUTER_SERVICE_ID} is not registered`);
    }
    return candidate;
};

export { ROUTER_SERVICE_ID, getRouterOptional, requireRouter };
