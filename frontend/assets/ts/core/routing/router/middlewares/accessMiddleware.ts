/* SoAI - Shared routing access middleware [frontend/assets/ts/core/routing/router/middlewares/accessMiddleware.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { canAccessUiSurface, createAccessContextFromAuth, createAccessRequirement, createRouteAccessRequirement } from '@core/access/accessPolicy.ts';
import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { navigationResult, type NavigationResultType } from '@core/navigationMiddleware.ts';
import { canAccessTerminal } from '@core/routing/router/terminalAccessPolicy.ts';
import type { ApiService, AuthService } from '@core/routing/router/routerDependencies.ts';
import type { NavigationContext } from '@core/routing/router/types.ts';

type RouterMiddleware = (context: NavigationContext, next: () => Promise<NavigationResultType>) => Promise<NavigationResultType>;

const buildForbiddenTarget = (component: string | null | undefined): string => (component ? `forbidden?page=${encodeURIComponent(component)}` : 'forbidden');

const createAdminOnlyAccessNavigationMiddleware = (auth: AuthService): RouterMiddleware => {
    return async (context: NavigationContext, next: () => Promise<NavigationResultType>): Promise<NavigationResultType> => {
        if (context.route.component === 'forbidden') {
            return next();
        }
        const requirement = createAccessRequirement({
            authenticated: context.route.auth === true,
            admin: context.route.adminOnly === true
        });
        const accessContext = createAccessContextFromAuth(auth, {
            terminalAllowed: true
        });
        if (!canAccessUiSurface(requirement, accessContext)) {
            return navigationResult.redirect(buildForbiddenTarget(context.route.component), { pushState: true });
        }
        return next();
    };
};

const createRouteActionAccessNavigationMiddleware = (auth: AuthService): RouterMiddleware => {
    return async (context: NavigationContext, next: () => Promise<NavigationResultType>): Promise<NavigationResultType> => {
        if (context.route.component === 'forbidden' || context.route.actions.length === 0) {
            return next();
        }
        if (auth.isAdmin()) {
            return next();
        }
        try {
            const permissions = await loadWebuiPermissionsSnapshot();
            const requirement = createRouteAccessRequirement(context.route);
            const accessContext = createAccessContextFromAuth(auth, {
                terminalAllowed: true,
                grantedActions: permissions.grantedActions
            });
            if (canAccessUiSurface(requirement, accessContext)) {
                return next();
            }
        } catch (error) {
            errorHandler.warn('Router', 'Failed to load route permissions snapshot', ensureError(error));
        }
        return navigationResult.redirect(buildForbiddenTarget(context.route.component), { pushState: true });
    };
};

const createTerminalAccessNavigationMiddleware = (auth: AuthService, api: ApiService): RouterMiddleware => {
    return async (context: NavigationContext, next: () => Promise<NavigationResultType>): Promise<NavigationResultType> => {
        if (context.route.component !== 'terminal') {
            return next();
        }
        const requirement = createAccessRequirement({
            authenticated: context.route.auth === true,
            terminal: true
        });
        const accessContext = createAccessContextFromAuth(auth, {
            terminalAllowed: await canAccessTerminal(auth, api)
        });
        if (canAccessUiSurface(requirement, accessContext)) {
            return next();
        }
        return navigationResult.redirect(buildForbiddenTarget(context.route.component), { pushState: true });
    };
};

export { createAdminOnlyAccessNavigationMiddleware, createRouteActionAccessNavigationMiddleware, createTerminalAccessNavigationMiddleware };
