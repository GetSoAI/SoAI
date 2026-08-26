/* SoAI - Shared routing wizard middleware [frontend/assets/ts/core/routing/router/middlewares/wizardMiddleware.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { navigationResult, type NavigationResultType } from '@core/navigationMiddleware.ts';
import { AUTH_ROUTE_LOGIN, AUTH_ROUTE_WIZARD } from '@core/routing/router/authRouteTarget.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { AuthService, StorageService } from '@core/routing/router/routerDependencies.ts';
import type { NavigationContext, RouteDefinition } from '@core/routing/router/types.ts';

type RouterMiddleware = (context: NavigationContext, next: () => Promise<NavigationResultType>) => Promise<NavigationResultType>;

const shouldRedirectToWizard = (auth: AuthService, storage: StorageService, route: RouteDefinition): boolean => {
    if (!isFunction(storage.isWizardCompletionPending)) {
        throw new Error('Storage service must expose wizard completion state');
    }
    if (typeof auth.isAuthenticated !== 'boolean') {
        throw new Error('Auth service must expose authentication state');
    }
    if (route.component === AUTH_ROUTE_WIZARD || route.component === AUTH_ROUTE_LOGIN) {
        return false;
    }
    return storage.isWizardCompletionPending() && auth.isAuthenticated === true;
};

const createWizardEnforcementNavigationMiddleware = (auth: AuthService, storage: StorageService): RouterMiddleware => {
    return async (context: NavigationContext, next: () => Promise<NavigationResultType>): Promise<NavigationResultType> => {
        if (shouldRedirectToWizard(auth, storage, context.route)) {
            return navigationResult.redirect(AUTH_ROUTE_WIZARD, { pushState: true });
        }
        return next();
    };
};

export { createWizardEnforcementNavigationMiddleware, shouldRedirectToWizard };
