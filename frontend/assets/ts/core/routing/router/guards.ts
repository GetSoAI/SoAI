/* SoAI - Shared routing router validation [frontend/assets/ts/core/routing/router/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { NAVIGATION_STATUS, navigationResult, type NavigationMiddlewareController, type NavigationResultType } from '@core/navigationMiddleware.ts';
import { normalizeMiddlewareOutcome } from '@core/routing/router/navigationMiddlewareNormalization.ts';
import { bindTerminalAccessPolicyInvalidation, canAccessTerminal, invalidateTerminalAccessPolicy } from '@core/routing/router/terminalAccessPolicy.ts';
import { createAuthEnforcementNavigationMiddleware } from '@core/routing/router/middlewares/authMiddleware.ts';
import { createAdminOnlyAccessNavigationMiddleware, createRouteActionAccessNavigationMiddleware, createTerminalAccessNavigationMiddleware } from '@core/routing/router/middlewares/accessMiddleware.ts';
import { createDirtyStateNavigationMiddleware } from '@core/routing/router/middlewares/dirtyStateMiddleware.ts';
import { createTelemetryNavigationMiddleware } from '@core/routing/router/middlewares/telemetryMiddleware.ts';
import { createWizardEnforcementNavigationMiddleware, shouldRedirectToWizard } from '@core/routing/router/middlewares/wizardMiddleware.ts';
import type { ApiService, AuthService, StorageService } from '@core/routing/router/routerDependencies.ts';
import type { NavigationContext, RouteDefinition, RouteParameters } from '@core/routing/router/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction } from '@core/typeGuards.ts';

type RouterMiddleware = (context: NavigationContext, next: () => Promise<NavigationResultType>) => Promise<NavigationResultType>;

interface RouterGuardDependencies {
    auth: AuthService;
    storage: StorageService;
    api: ApiService;
    emitRouterEvent: (stage: string, data?: Record<string, JsonValue | null | undefined>, severity?: string) => void;
}

interface NavigationMiddlewareRegistration {
    priority: number;
    middleware: RouterMiddleware;
}

const bindTerminalAccessInvalidation = (auth: AuthService): void => {
    bindTerminalAccessPolicyInvalidation();
    auth.onLogin(() => {
        invalidateTerminalAccessPolicy();
    });
    auth.onLogout(() => {
        invalidateTerminalAccessPolicy();
    });
};

const createCoreNavigationMiddlewareRegistrations = (dependencies: RouterGuardDependencies): NavigationMiddlewareRegistration[] => {
    return [
        {
            priority: 300,
            middleware: createTelemetryNavigationMiddleware(dependencies.emitRouterEvent)
        },
        {
            priority: 250,
            middleware: createWizardEnforcementNavigationMiddleware(dependencies.auth, dependencies.storage)
        },
        {
            priority: 200,
            middleware: createAuthEnforcementNavigationMiddleware(dependencies.auth, dependencies.storage)
        },
        {
            priority: 190,
            middleware: createAdminOnlyAccessNavigationMiddleware(dependencies.auth)
        },
        {
            priority: 185,
            middleware: createRouteActionAccessNavigationMiddleware(dependencies.auth)
        },
        {
            priority: 150,
            middleware: createTerminalAccessNavigationMiddleware(dependencies.auth, dependencies.api)
        },
        {
            priority: 100,
            middleware: createDirtyStateNavigationMiddleware()
        }
    ];
};

const toNavigationResultType = (value: NavigationResultType | boolean | void | null): NavigationResultType => {
    const outcome = normalizeMiddlewareOutcome(value);
    if (outcome.status === NAVIGATION_STATUS.BLOCKED) {
        return navigationResult.block(outcome.reason ?? null);
    }
    if (outcome.status === NAVIGATION_STATUS.REDIRECT) {
        const target = outcome.target ?? '';
        if (!target) {
            return navigationResult.continue();
        }
        const options = outcome.options ? { ...outcome.options } : {};
        return navigationResult.redirect(target, options);
    }
    if (outcome.status === NAVIGATION_STATUS.CONTINUE) {
        return navigationResult.continue(outcome.detail ?? null);
    }
    return navigationResult.continue();
};

const useRouterNavigationMiddleware = (controller: NavigationMiddlewareController, middleware: RouterMiddleware, options: { priority: number }): (() => void) => {
    if (!isFunction(middleware)) {
        throw new Error('Router requires middleware functions to be callable');
    }
    return controller.use(async (context: NavigationContext, next: () => Promise<NavigationResultType>) => toNavigationResultType(await middleware(context, next)), options);
};

const registerCoreNavigationMiddleware = (dependencies: RouterGuardDependencies, useMiddleware: (middleware: RouterMiddleware, options: { priority: number }) => () => void): void => {
    bindTerminalAccessInvalidation(dependencies.auth);
    const registrations = createCoreNavigationMiddlewareRegistrations(dependencies);
    for (const registration of registrations) {
        useMiddleware(registration.middleware, { priority: registration.priority });
    }
};

const createBeforeNavigateMiddleware = (callback: (route: RouteDefinition, parameters: RouteParameters, context: NavigationContext) => Promise<boolean | void | NavigationResultType | null>): RouterMiddleware => {
    if (!isFunction(callback)) {
        throw new Error('Router beforeNavigate callback must be callable');
    }
    return async (context: NavigationContext, next: () => Promise<NavigationResultType>): Promise<NavigationResultType> => {
        const result = await callback(context.route, context.parameters, context);
        if (result === false) {
            return navigationResult.block('beforeNavigate');
        }
        const outcome = normalizeMiddlewareOutcome(result);
        if (outcome.status !== NAVIGATION_STATUS.CONTINUE) {
            return outcome;
        }
        return next();
    };
};

export { canAccessTerminal, createBeforeNavigateMiddleware, createCoreNavigationMiddlewareRegistrations, registerCoreNavigationMiddleware, shouldRedirectToWizard, useRouterNavigationMiddleware };
export type { NavigationMiddlewareRegistration, RouterGuardDependencies, RouterMiddleware };
