/* SoAI - Authorized power mode navigation wiring [frontend/assets/ts/app/bootstrap/navigation/powerMode.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AuthManager } from '@core/auth/service.ts';
import { navigationResult } from '@core/navigationMiddleware.ts';
import { onNavigationComplete, onNavigationStart, onNavigationError } from '@core/navigationEvents.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { PowerModeController, type PowerModeDependencies } from '@features/power/public.ts';

const wirePowerMode = (dependencies: Omit<PowerModeDependencies, 'subscribe' | 'canAccess'> & { router: Router; auth: AuthManager }): PowerModeController => {
    const { router, auth } = dependencies;
    const resources = new ResourceTracker();
    if (!router.resources.track) throw new Error('Power mode requires tracked router resources');
    router.resources.track(resources);
    const mode = new PowerModeController({
        ...dependencies,
        canAccess: () => auth.isAuthenticated && auth.isAdmin(),
        subscribe: (resource, handler) => getStreamRuntime().subscriptions.subscribeResourceValue(resource, handler)
    });
    let directRequest: { action: string | undefined; landing: string } | null = null;
    let generation = 0;
    resources.track(
        router.useNavigationMiddleware(
            async (context, next) => {
                generation += 1;
                if (context.route.component !== 'power') {
                    if (context.route.auth && auth.isAdmin() && mode.isSubmitting()) return navigationResult.block('power-submitting');
                    return next();
                }
                if (context.from && context.from.route.auth && context.from.route.component !== 'power') {
                    const currentRoute = router.getCurrentRoute();
                    const hashRoute = router.getRouteFromHash();
                    if (currentRoute && hashRoute && router.parseRoute(hashRoute)?.route.component === 'power') router.replaceCurrentRoute(currentRoute);
                    await mode.open(context.parameters['action'], context.signal);
                    return navigationResult.block('power-mode-opened');
                }
                const preferred = router.getDefaultRoute();
                const landing = router.parseRoute(preferred)?.route.component === 'power' ? 'dashboard' : preferred;
                directRequest = { action: context.parameters['action'], landing };
                return navigationResult.redirect(landing, { replace: true, pushState: true });
            },
            { priority: 175 }
        )
    );
    resources.track(
        onNavigationStart((detail) => {
            mode.closePresentation();
            if (detail?.route !== directRequest?.landing) directRequest = null;
        })
    );
    resources.track(
        onNavigationError(() => {
            directRequest = null;
        })
    );
    resources.track(
        onNavigationComplete((detail) => {
            const requested = directRequest;
            if (!requested || requested.landing !== detail?.route) return;
            directRequest = null;
            const openedGeneration = generation;
            terminateHandledPromise(
                (async (): Promise<void> => {
                    await router.pageOutlet.waitForCommit();
                    if (generation === openedGeneration) await mode.open(requested.action);
                })()
            );
        })
    );
    resources.track(
        auth.onLogin(() => {
            mode.accessChanged();
        })
    );
    resources.track(
        auth.onLogout(() => {
            directRequest = null;
            mode.accessChanged();
        })
    );
    resources.track({ dispose: () => mode.destroy() });
    return mode;
};

export { wirePowerMode };
