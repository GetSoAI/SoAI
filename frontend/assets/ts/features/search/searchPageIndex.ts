/* SoAI - Search feature page index [frontend/assets/ts/features/search/searchPageIndex.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { canAccessUiSurface, createAccessContextFromAuth, createRouteAccessRequirement } from '@core/access/accessPolicy.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { getRouteRegistry } from '@core/routeregistry/service.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';

const buildPageIndexEntries = (grantedActions: ReadonlySet<string> = new Set()): SearchItem[] => {
    const routeRegistry = getRouteRegistry();
    const auth = getAuthManager();
    const accessContext = createAccessContextFromAuth(auth, {
        terminalAllowed: grantedActions.has('TERMINAL_USE'),
        grantedActions
    });
    return Object.values(routeRegistry)
        .filter((route) => {
            if (route.search?.include !== true) {
                return false;
            }
            return canAccessUiSurface(createRouteAccessRequirement(route), accessContext);
        })
        .map((route) => {
            const search = route.search;
            if (!search) {
                throw new Error(`Search page index route "${route.id}" is missing search metadata`);
            }
            return {
                id: route.id,
                name: search.getTitle ? search.getTitle() : route.getTitle(),
                description: search.getDescription(),
                type: 'page',
                category: 'page'
            };
        });
};

export { buildPageIndexEntries };
