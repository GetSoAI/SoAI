/* SoAI - Shared routing base page layout state [frontend/assets/ts/core/routing/pages/basepagelayout/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageActionsMenuManager } from '@core/pageActionsMenu.ts';
import type { TabsComponent } from '@core/ui/controls/Tabs.ts';

interface HeaderStatsLayout {
    readonly container: HTMLElement;
}

interface BasePageLayoutState {
    tabs: TabsComponent | null;
    layoutResizeObserver: ResizeObserver | null;
    pendingLayoutFrame: number | null;
    pendingHeaderStatsFrame: number | null;
    headerStatsLayouts: HeaderStatsLayout[] | null;
    ctaLinkDisposer: (() => void) | null;
    responsiveSetup: boolean;
    pendingHeaderActionsFrame: number | null;
    pageActionsMenu: PageActionsMenuManager | null;
    prefixedSelectObserver: MutationObserver | null;
    externalLinkTargets: WeakSet<Element> | null;
}

const createBasePageLayoutState = (): BasePageLayoutState => ({
    tabs: null,
    layoutResizeObserver: null,
    pendingLayoutFrame: null,
    pendingHeaderStatsFrame: null,
    headerStatsLayouts: null,
    ctaLinkDisposer: null,
    responsiveSetup: false,
    pendingHeaderActionsFrame: null,
    pageActionsMenu: null,
    prefixedSelectObserver: null,
    externalLinkTargets: null
});

export type { HeaderStatsLayout, BasePageLayoutState };
export { createBasePageLayoutState };
