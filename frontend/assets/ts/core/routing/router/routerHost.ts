/* SoAI - Shared routing router host [frontend/assets/ts/core/routing/router/routerHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RouteEntry, RouteParameters } from '@core/routing/router/types.ts';

interface RouterHost {
    ensureInitialized: () => void;
    parseRoute: (routePath: string) => { route: RouteEntry; parameters: RouteParameters } | null;
    reload: () => Promise<void>;
}

export type { RouterHost };
