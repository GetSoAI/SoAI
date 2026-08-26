/* SoAI - Shared routing router connection hold [frontend/assets/ts/core/routing/router/routerConnectionHold.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getConnectionStatusRuntime, type ConnectionStatusRuntime } from '@core/connectionstatus/runtime.ts';

type NavigationConnectionHoldToken = ReturnType<ConnectionStatusRuntime['retainConnection']> | null;
type ConnectionStatusService = ConnectionStatusRuntime;

const resolveConnectionStatusService = (): ConnectionStatusService | null => getConnectionStatusRuntime();

const acquireNavigationConnectionHold = (): NavigationConnectionHoldToken => {
    const service = resolveConnectionStatusService();
    return service ? service.retainConnection('router:navigation', { timeoutMs: 4000 }) : null;
};

const releaseNavigationConnectionHold = (token: NavigationConnectionHoldToken): boolean => {
    const service = resolveConnectionStatusService();
    return token !== null && service !== null ? service.releaseConnection(token, { reason: 'router:navigation' }) : false;
};

export type { ConnectionStatusService, NavigationConnectionHoldToken };
export { acquireNavigationConnectionHold, releaseNavigationConnectionHold };
