/* SoAI - Chat page route synchronization [frontend/assets/ts/pages/chat/controllers/navigation/routeSynchronization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { buildChatBaseRoute, buildChatConversationRoute } from '@features/chat/public.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageRouting } from '@core/routing/router/types.ts';
import { buildQueryRoute } from '@core/routing/router/queryParameters.ts';

interface RouteReplacementHost extends PageServicesOwnerHost {
    router: Pick<PageRouting, 'replaceCurrentRoute' | 'navigate' | 'getCurrentRoute' | 'getQueryParameters' | 'parseRoute'>;
}

const hasActiveRoute = (route: string | null): route is string => typeof route === 'string' && route.length > 0;
const isRouteOwnedByAnotherPage = (router: RouteReplacementHost['router'], route: string | null): boolean => hasActiveRoute(route) && router.parseRoute(route)?.route.component !== 'chat';

const replaceChatConversationRoute = async (host: RouteReplacementHost, conversationId: string | null, options: { signal?: AbortSignal | null } = {}): Promise<void> => {
    const signal = options.signal ?? null;
    if (host.services.isDetached() || signal?.aborted) {
        return;
    }
    const targetRoute = conversationId ? buildChatConversationRoute(conversationId) : buildChatBaseRoute();
    const router = host.router;
    const currentRoute = router.getCurrentRoute();
    if (isRouteOwnedByAnotherPage(router, currentRoute)) {
        return;
    }
    if (!hasActiveRoute(currentRoute)) {
        if (signal?.aborted || isRouteOwnedByAnotherPage(router, router.getCurrentRoute())) {
            return;
        }
        await router.navigate(targetRoute, { replace: true });
        return;
    }
    if (signal?.aborted || isRouteOwnedByAnotherPage(router, router.getCurrentRoute())) {
        return;
    }

    try {
        router.replaceCurrentRoute(buildQueryRoute(targetRoute, router.getQueryParameters()));
        return;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('Chat route sync', 'Replacing current conversation route failed', runtimeError);
        throw runtimeError;
    }
};

export { replaceChatConversationRoute };
export type { RouteReplacementHost };
