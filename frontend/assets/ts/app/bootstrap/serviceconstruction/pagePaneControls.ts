/* SoAI - Pane target composition using the shared sidebar access policy [frontend/assets/ts/app/bootstrap/serviceconstruction/pagePaneControls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AuthManager } from '@core/auth/public.ts';
import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { WebuiPermissionsUnavailableError } from '@core/access/permissionFailure.ts';
import { createSidebarStaticConfig, cloneSidebarConfigEntries } from '@core/layout/sidebar/adapters.ts';
import { getVisibleSidebarConfig } from '@core/layout/sidebar/service.ts';
import { getRouteRegistry } from '@core/routeregistry/service.ts';
import { PagePaneControls, type PagePaneControlsDependencies } from '@core/pagepanes/controls.ts';

const createBootstrapPagePaneControls = (dependencies: Omit<PagePaneControlsDependencies, 'readTargets' | 'auth'> & { readonly auth: AuthManager }): PagePaneControls =>
    new PagePaneControls({
        ...dependencies,
        readTargets: async (signal) => {
            try {
                const permissions = await loadWebuiPermissionsSnapshot({ signal });
                const config = createSidebarStaticConfig();
                const visible = getVisibleSidebarConfig(cloneSidebarConfigEntries(config.defaultSidebarConfig), config.adminOnlyItems, dependencies.auth.user, permissions.grantedActions);
                const registry = getRouteRegistry();
                const targets = visible.flatMap((entry) => {
                    if (entry.type !== 'page' || !entry.id) return [];
                    const route = registry[entry.id];
                    if (!route) throw new Error('Pane target requires its registered sidebar route');
                    return route.auth && !route.layout.exclusive && route.sidebar?.activateOnNavigation !== false ? [route] : [];
                });
                return { type: 'ready', targets };
            } catch (error) {
                if (error instanceof WebuiPermissionsUnavailableError) return { type: 'unavailable', error };
                throw error;
            }
        }
    });

export { createBootstrapPagePaneControls };
