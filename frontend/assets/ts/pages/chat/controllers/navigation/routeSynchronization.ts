/* SoAI - Chat page route synchronization [frontend/assets/ts/pages/chat/controllers/navigation/routeSynchronization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { buildChatBaseRoute, buildChatConversationRoute } from '@features/chat/public.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';

interface RouteReplacementHost extends PageServicesOwnerHost {
    router: {
        replaceCurrentRoute(target: string): void;
        navigate(target: string, options?: { replace?: boolean }): Promise<void> | void;
        getCurrentRoute(): string | null;
        getRouteFromHash(): string | null;
    };
}

const isChatOwnedRoute = (route: string | null): boolean => route === buildChatBaseRoute() || (typeof route === 'string' && route.startsWith(`${buildChatBaseRoute()}/conversation/`));
const hasActiveRoute = (route: string | null): route is string => typeof route === 'string' && route.length > 0;
const isRouteOwnedByAnotherPage = (route: string | null): boolean => hasActiveRoute(route) && !isChatOwnedRoute(route);

const replaceChatConversationRoute = async (host: RouteReplacementHost, conversationId: string | null, options: { signal?: AbortSignal | null } = {}): Promise<void> => {
    const signal = options.signal ?? null;
    if (host.services.isDetached() || signal?.aborted) {
        return;
    }
    const targetRoute = conversationId ? buildChatConversationRoute(conversationId) : buildChatBaseRoute();
    const router = host.router;
    const currentRoute = router.getCurrentRoute();
    const locationRoute = router.getRouteFromHash();
    if (isRouteOwnedByAnotherPage(currentRoute) || isRouteOwnedByAnotherPage(locationRoute)) {
        return;
    }
    if (!hasActiveRoute(currentRoute)) {
        if (signal?.aborted || isRouteOwnedByAnotherPage(router.getRouteFromHash())) {
            return;
        }
        await router.navigate(targetRoute, { replace: true });
        return;
    }
    if (signal?.aborted || isRouteOwnedByAnotherPage(router.getRouteFromHash())) {
        return;
    }

    try {
        router.replaceCurrentRoute(targetRoute);
        return;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('Chat route sync', 'Replacing current conversation route failed', runtimeError);
        throw runtimeError;
    }
};

export { replaceChatConversationRoute };
export type { RouteReplacementHost };
