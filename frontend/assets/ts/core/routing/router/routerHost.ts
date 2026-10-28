/* SoAI - Shared routing router host [frontend/assets/ts/core/routing/router/routerHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RouteEntry, RouteParameters, NavigationOptions } from '@core/routing/router/types.ts';

interface RouterHost {
    initialized: boolean;
    isBrowserNavigationSuspended(): boolean;
    getCurrentRoute(): string | null;
    getRouteFromHash(): string | null;
    getLatestNavigationCompletion(): Promise<void> | null;
    navigate(route: string, options: NavigationOptions): Promise<void>;
    ensureInitialized: () => void;
    parseRoute: (routePath: string) => { route: RouteEntry; parameters: RouteParameters } | null;
    reload: () => Promise<void>;
}

export type { RouterHost };
