/* SoAI - Shared layout route lifecycle [frontend/assets/ts/core/layout/sidebar/routeLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { onNavigationComplete, onNavigationStart, type NavigationEventDetail } from '@core/navigationEvents.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { normalizeRoute } from '@core/layout/sidebar/foundation.ts';
import { resolveComponentFromNavigationDetail, resolveRouteFromNavigationDetail } from '@core/layout/sidebar/navigation.ts';

interface SidebarRouteStartListenerDependencies {
    addPersistentDisposer: (functionValue: (() => void) | null | undefined) => () => void;
    enqueueRouteChange: (routeValue: string | null, options: { allowActiveSync: boolean }) => Promise<void>;
}

interface SidebarNavigationCompleteListenerDependencies extends SidebarRouteStartListenerDependencies {
    getCurrentRoute: () => string | null;
    markChatTerminalIndicatorsSeen: () => void;
}

interface SidebarRouteProcessingDependencies {
    getCurrentRoute: () => string | null;
    getRouteFromHash: () => string | null;
    routeBlocklist: Set<string>;
    needsBootstrap: () => boolean;
    bootstrapSidebar: () => Promise<void>;
    teardownSidebar: () => Promise<void>;
    syncWithCurrentRoute: () => void;
    updateMainStateIndicator: () => void;
}

const createSidebarRouteStartListener = (dependencies: SidebarRouteStartListenerDependencies): (() => void) => {
    return dependencies.addPersistentDisposer(
        onNavigationStart(async (detail: NavigationEventDetail | null = null) => {
            try {
                const routeValue = resolveRouteFromNavigationDetail(detail);
                await dependencies.enqueueRouteChange(routeValue, { allowActiveSync: false });
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('Sidebar', 'Route transition failed', runtimeError);
            }
        })
    );
};

const createSidebarNavigationCompleteListener = (dependencies: SidebarNavigationCompleteListenerDependencies): (() => void) => {
    return dependencies.addPersistentDisposer(
        onNavigationComplete(async (detail: NavigationEventDetail | null = null) => {
            const componentValue = resolveComponentFromNavigationDetail(detail);
            try {
                const routeValue = resolveRouteFromNavigationDetail(detail);
                await dependencies.enqueueRouteChange(routeValue, { allowActiveSync: true });
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('Sidebar', 'Route completion sync failed', runtimeError);
            }

            const destination = normalizeRoute(componentValue) || normalizeRoute(resolveRouteFromNavigationDetail(detail)) || normalizeRoute(dependencies.getCurrentRoute()) || null;

            if (destination === 'chat') {
                dependencies.markChatTerminalIndicatorsSeen();
            }
        })
    );
};

const processSidebarRoute = async (dependencies: SidebarRouteProcessingDependencies, routeValue: string | null, options: { allowActiveSync: boolean }): Promise<void> => {
    const normalized = normalizeRoute(routeValue) || normalizeRoute(dependencies.getCurrentRoute()) || normalizeRoute(dependencies.getRouteFromHash()) || null;

    if (!normalized) {
        if (dependencies.needsBootstrap()) {
            await dependencies.bootstrapSidebar();
        }
        if (options.allowActiveSync) {
            dependencies.syncWithCurrentRoute();
        }
        dependencies.updateMainStateIndicator();
        return;
    }

    if (dependencies.routeBlocklist.has(normalized)) {
        await dependencies.teardownSidebar();
        return;
    }

    if (dependencies.needsBootstrap()) {
        await dependencies.bootstrapSidebar();
    }
    if (options.allowActiveSync) {
        dependencies.syncWithCurrentRoute();
    }
    dependencies.updateMainStateIndicator();
};

export { createSidebarNavigationCompleteListener, createSidebarRouteStartListener, processSidebarRoute };
