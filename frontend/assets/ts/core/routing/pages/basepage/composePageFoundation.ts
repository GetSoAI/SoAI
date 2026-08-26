/* SoAI - Routed page foundation owner composition [frontend/assets/ts/core/routing/pages/basepage/composePageFoundation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AuthManager } from '@core/auth/public.ts';
import type { loadingState } from '@core/loadingState.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import { PageCollapsibleCards } from '@core/routing/pages/basepagelayout/PageCollapsibleCards.ts';
import { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { LanguageService } from '@core/routing/pages/pagetypes/public.ts';
import { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';

interface PageFoundationDependencies {
    pageId: string;
    auth: AuthManager;
    languageService: LanguageService;
    loading: typeof loadingState;
    pageContext: PageContext;
    pageDom: PageDom;
    pageHost: PageHost;
    resources: PageResources;
    router: Router;
    storage: StorageService;
}

interface PageFoundation {
    services: PageServices;
    layout: PageLayout;
    pageElements: PageUi;
    collapsibleCards: PageCollapsibleCards;
    streaming: PageStreaming;
    pageLifecycle: PageLifecycle;
}

const composePageFoundation = (dependencies: PageFoundationDependencies): PageFoundation => {
    const services = new PageServices({
        pageId: dependencies.pageId,
        pageContext: dependencies.pageContext,
        loadingState: dependencies.loading,
        storage: dependencies.storage,
        router: dependencies.router,
        auth: dependencies.auth,
        languageService: dependencies.languageService,
        pageDom: dependencies.pageDom,
        resources: dependencies.resources
    });
    const layout = new PageLayout(
        {
            pageId: dependencies.pageId,
            pageContext: dependencies.pageContext,
            pageDom: dependencies.pageDom,
            pageHost: dependencies.pageHost,
            resources: dependencies.resources,
            services
        },
        {}
    );
    const pageElements = new PageUi({ loadingState: dependencies.loading, layout, pageDom: dependencies.pageDom });
    layout.configure({ updateCheckerboard: () => pageElements.updateCheckerboard() });
    const collapsibleCards = new PageCollapsibleCards({
        pageDom: dependencies.pageDom,
        pageElements,
        resources: dependencies.resources,
        storage: dependencies.storage
    });
    const streaming = new PageStreaming({ pageId: dependencies.pageId, pageContext: dependencies.pageContext, pageElements, resources: dependencies.resources });
    const pageLifecycle = new PageLifecycle({
        pageId: dependencies.pageId,
        services,
        layout,
        streaming,
        resources: dependencies.resources,
        pageDom: dependencies.pageDom,
        pageHost: dependencies.pageHost,
        pageElements,
        collapsibleCards
    });
    return { services, layout, pageElements, collapsibleCards, streaming, pageLifecycle };
};

export { composePageFoundation };
export type { PageFoundation, PageFoundationDependencies };
