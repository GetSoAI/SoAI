/* SoAI - Shared routing auth middleware [frontend/assets/ts/core/routing/router/middlewares/authMiddleware.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { throwIfAborted } from '@core/errors/abort.ts';
import { shouldRedirectToWizard } from '@core/routing/router/middlewares/wizardMiddleware.ts';
import { NAVIGATION_STATUS, navigationResult, type NavigationResultType } from '@core/navigationMiddleware.ts';
import { isAiSetupResumeRequest } from '@core/routing/router/aiSetupRoutes.ts';
import { AUTH_ROUTE_LOGIN, AUTH_ROUTE_WIZARD, resolveAuthenticatedRouteTarget } from '@core/routing/router/authRouteTarget.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { AuthService, StorageService } from '@core/routing/router/routerDependencies.ts';
import type { NavigationContext } from '@core/routing/router/types.ts';

type RouterMiddleware = (context: NavigationContext, next: () => Promise<NavigationResultType>) => Promise<NavigationResultType>;

const resolveAuthenticatedNavigation = (auth: AuthService, storage: StorageService, context: NavigationContext): NavigationResultType | null => {
    if (!auth.isAuthenticated) return null;
    const route = context.route;
    if (route.component === AUTH_ROUTE_WIZARD) {
        if (!isFunction(storage.isWizardCompletionPending)) {
            throw new Error('Storage service must expose wizard completion state');
        }
        if (storage.isWizardCompletionPending()) {
            return navigationResult.continue();
        }
        if (isAiSetupResumeRequest(context.parameters) && auth.isAdmin() && storage.isAiSetupResumable()) {
            return navigationResult.continue();
        }
    }
    if (route.component === AUTH_ROUTE_LOGIN || route.component === AUTH_ROUTE_WIZARD) {
        if (context.router === null) {
            throw new Error('Navigation context router must expose parseRoute and getDefaultRoute');
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
    return navigationResult.continue();
};

const createAuthEnforcementNavigationMiddleware = (auth: AuthService, storage: StorageService): RouterMiddleware => {
    return async (context: NavigationContext, next: () => Promise<NavigationResultType>): Promise<NavigationResultType> => {
        const route = context.route;
        throwIfAborted(context.signal);
        const authenticated = resolveAuthenticatedNavigation(auth, storage, context);
        if (authenticated) return authenticated.status === NAVIGATION_STATUS.CONTINUE ? next() : authenticated;
        if (route.auth !== true) return next();

        const pendingSetup = isFunction(auth.checkWizardStatus) ? await auth.checkWizardStatus() : false;
        throwIfAborted(context.signal);
        if (pendingSetup || shouldRedirectToWizard(auth, storage, route)) {
            return navigationResult.redirect(AUTH_ROUTE_WIZARD, { pushState: true });
        }

        const authenticatedAfterLookup = resolveAuthenticatedNavigation(auth, storage, context);
        if (authenticatedAfterLookup) return authenticatedAfterLookup.status === NAVIGATION_STATUS.CONTINUE ? next() : authenticatedAfterLookup;

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
