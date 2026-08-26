/* SoAI - Shared routing auth middleware [frontend/assets/ts/core/routing/router/middlewares/authMiddleware.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { navigationResult, type NavigationResultType } from '@core/navigationMiddleware.ts';
import { AUTH_ROUTE_LOGIN, AUTH_ROUTE_WIZARD, resolveAuthenticatedRouteTarget } from '@core/routing/router/authRouteTarget.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { AuthService, StorageService } from '@core/routing/router/routerDependencies.ts';
import type { NavigationContext } from '@core/routing/router/types.ts';

type RouterMiddleware = (context: NavigationContext, next: () => Promise<NavigationResultType>) => Promise<NavigationResultType>;

const createAuthEnforcementNavigationMiddleware = (auth: AuthService, storage: StorageService): RouterMiddleware => {
    return async (context: NavigationContext, next: () => Promise<NavigationResultType>): Promise<NavigationResultType> => {
        const route = context.route;
        if (auth.isAuthenticated && route.component === AUTH_ROUTE_WIZARD) {
            if (!isFunction(storage.isWizardCompletionPending)) {
                throw new Error('Storage service must expose wizard completion state');
            }
            if (storage.isWizardCompletionPending()) {
                return next();
            }
        }
        if (auth.isAuthenticated && (route.component === AUTH_ROUTE_LOGIN || route.component === AUTH_ROUTE_WIZARD)) {
            if (context.router === null) {
                throw new Error('Navigation context router must expose parseRoute');
            }
            const redirectAfterLogin = storage.getRedirectAfterLogin();
            const target = resolveAuthenticatedRouteTarget(context.router, {
                currentRoute: context.request.path || route.path,
                redirectAfterLogin
            });
            if (redirectAfterLogin && target === redirectAfterLogin) {
                storage.clearRedirectAfterLogin();
            }
            return navigationResult.redirect(target, { pushState: true });
        }
        if (route.auth !== true || auth.isAuthenticated) {
            return next();
        }

        const pendingSetup = isFunction(auth.checkWizardStatus) ? await auth.checkWizardStatus() : false;
        if (pendingSetup) {
            return navigationResult.redirect(AUTH_ROUTE_WIZARD, { pushState: true });
        }

        if (route.component === AUTH_ROUTE_LOGIN) {
            return navigationResult.block('login-route');
        }

        if (!isFunction(storage.setRedirectAfterLogin)) {
            throw new Error('Storage service must expose setRedirectAfterLogin');
        }
        storage.setRedirectAfterLogin(context.request.path || route.path);
        return navigationResult.redirect(AUTH_ROUTE_LOGIN, { pushState: true });
    };
};

export { createAuthEnforcementNavigationMiddleware };
