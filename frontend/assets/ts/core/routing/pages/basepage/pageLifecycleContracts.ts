/* SoAI - Routed page lifecycle command contracts [frontend/assets/ts/core/routing/pages/basepage/pageLifecycleContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageRuntimePhases } from '@core/runtime/pageRuntimeContracts.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageCollapsibleCards } from '@core/routing/pages/basepagelayout/PageCollapsibleCards.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface PageInitializationCommand {
    render(parameters?: JsonObject | null): Promise<TrustedHtml>;
    refresh(parameters: JsonObject | null, context: { signal?: AbortSignal }): Promise<void>;
    initializeDomain(parameters: JsonObject | null, context: { signal?: AbortSignal }): Promise<void>;
    readiness: PageRuntimePhases;
}

interface PageLifecycleDependencies {
    pageId: string;
    services: PageServices;
    layout: PageLayout;
    streaming: PageStreaming;
    resources: PageResources;
    pageDom: PageDom;
    pageHost: PageHost;
    pageElements: PageUi;
    collapsibleCards: PageCollapsibleCards;
}

interface PageRefreshCommand {
    beforeCleanup(): void;
    getRequiredResources(): string[];
    refreshDomainState(): void;
    onInitialize(parameters: JsonObject | null, context: { signal?: AbortSignal }): Promise<void>;
}

interface PageDestroyCommand {
    onDestroy(): Promise<void>;
    cleanupDomainState(): void;
    onCollectionStateCleaned(): void;
}

export type { PageDestroyCommand, PageInitializationCommand, PageLifecycleDependencies, PageRefreshCommand };
