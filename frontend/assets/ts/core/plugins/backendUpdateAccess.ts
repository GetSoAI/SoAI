/* SoAI - Backend management permission and route access [frontend/assets/ts/core/plugins/backendUpdateAccess.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { canAccessUiSurface, createAccessContext, createRouteAccessRequirement } from '@core/access/accessPolicy.ts';
import type { WebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { getRouteDefinitions } from '@core/routeregistry/service.ts';

const canManagePluginBackends = (permissions: WebuiPermissionsSnapshot): boolean => {
    if (!permissions.grantedActions.has('PLUGIN_READ') || !permissions.grantedActions.has('PLUGIN_ADMIN')) return false;
    const route = getRouteDefinitions().find((candidate) => candidate.component === 'plugins');
    return route !== undefined && canAccessUiSurface(createRouteAccessRequirement(route), createAccessContext({ isAuthenticated: true, isAdmin: permissions.isAdmin, grantedActions: permissions.grantedActions }));
};

export { canManagePluginBackends };
