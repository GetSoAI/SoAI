/* SoAI - Shared layout sidebar events [frontend/assets/ts/core/layout/sidebar/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createSidebarNavigationCompleteListener, createSidebarRouteStartListener, processSidebarRoute } from '@core/layout/sidebar/routeLifecycle.ts';

type SidebarRouteChangeEnqueuer = (routeValue: string | null, options?: { allowActiveSync: boolean }) => Promise<void>;

interface SidebarRouteEventsContext {
    addPersistentDisposer: (functionValue: (() => void) | null | undefined) => () => void;
    routeBlocklist: Set<string>;
    getMenuElement: () => HTMLElement | null;
    getCurrentRoute: () => string | null;
    getRouteFromHash: () => string | null;
    isInitialized: () => boolean;
    hasSidebarReadyClass: () => boolean;
    bootstrapSidebar: () => Promise<void>;
    teardownSidebar: () => Promise<void>;
    syncWithCurrentRoute: () => void;
    updateMainStateIndicator: () => void;
    markChatTerminalIndicatorsSeen: () => void;
    runRouteTask: (task: () => Promise<void>) => Promise<void>;
}

const bindSidebarRouteEvents = (context: SidebarRouteEventsContext): SidebarRouteChangeEnqueuer => {
    const enqueueRouteChange: SidebarRouteChangeEnqueuer = (routeValue: string | null, options: { allowActiveSync: boolean } = { allowActiveSync: true }): Promise<void> =>
        context.runRouteTask(() =>
            processSidebarRoute(
                {
                    getCurrentRoute: () => context.getCurrentRoute(),
                    getRouteFromHash: () => context.getRouteFromHash(),
                    routeBlocklist: context.routeBlocklist,
                    needsBootstrap: () => {
                        const menu = context.getMenuElement();
                        return !context.isInitialized() || !menu || !menu.childElementCount || !context.hasSidebarReadyClass();
                    },
                    bootstrapSidebar: () => context.bootstrapSidebar(),
                    teardownSidebar: () => context.teardownSidebar(),
                    syncWithCurrentRoute: () => context.syncWithCurrentRoute(),
                    updateMainStateIndicator: () => context.updateMainStateIndicator()
                },
                routeValue,
                options
            )
        );

    createSidebarRouteStartListener({
        addPersistentDisposer: (functionValue) => context.addPersistentDisposer(functionValue),
        enqueueRouteChange: (routeValue, options) => enqueueRouteChange(routeValue, options)
    });

    createSidebarNavigationCompleteListener({
        addPersistentDisposer: (functionValue) => context.addPersistentDisposer(functionValue),
        enqueueRouteChange: (routeValue, options) => enqueueRouteChange(routeValue, options),
        getCurrentRoute: () => context.getCurrentRoute(),
        markChatTerminalIndicatorsSeen: () => context.markChatTerminalIndicatorsSeen()
    });

    return enqueueRouteChange;
};

export { bindSidebarRouteEvents };
export type { SidebarRouteChangeEnqueuer, SidebarRouteEventsContext };
