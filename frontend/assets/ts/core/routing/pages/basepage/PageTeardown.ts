/* SoAI - Routed page deterministic teardown ownership [frontend/assets/ts/core/routing/pages/basepage/PageTeardown.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { getOptionalCheckerboardService } from '@core/routing/pages/pageDom.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageCollapsibleCards } from '@core/routing/pages/basepagelayout/PageCollapsibleCards.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';

interface PageTeardownDependencies {
    pageId: string;
    services: PageServices;
    layout: PageLayout;
    streaming: PageStreaming;
    resources: PageResources;
    pageDom: PageDom;
    pageElements: PageUi;
    collapsibleCards: PageCollapsibleCards;
}

class PageTeardown {
    readonly #dependencies: PageTeardownDependencies;
    #cleanupPerformed = false;
    #cleanupTask: Promise<boolean> | null = null;

    constructor(dependencies: PageTeardownDependencies) {
        this.#dependencies = dependencies;
    }

    reset(): void {
        this.#cleanupPerformed = false;
        this.#cleanupTask = null;
    }

    async #attempt(label: string, operation: () => Promise<void> | void): Promise<void> {
        try {
            await operation();
        } catch (error) {
            errorHandler.error(this.#dependencies.pageId, label, ensureError(error));
        }
    }

    async destroyOwnedState(): Promise<void> {
        await this.#attempt('Page collapsible-card destruction failed', () => this.#dependencies.collapsibleCards.reset());
        await this.#attempt('Page layout destruction failed', () => this.#dependencies.layout.destroy());
        await this.#attempt('Page stream destruction failed', () => this.#dependencies.streaming.destroy());
    }

    async cleanup(cleanupDomainState: () => void, onCollectionStateCleaned: () => void): Promise<boolean> {
        if (this.#cleanupPerformed) return false;
        if (this.#cleanupTask) return await this.#cleanupTask;
        this.#cleanupTask = this.#runCleanup(cleanupDomainState, onCollectionStateCleaned);
        try {
            return await this.#cleanupTask;
        } finally {
            this.#cleanupTask = null;
        }
    }

    async #runCleanup(cleanupDomainState: () => void, onCollectionStateCleaned: () => void): Promise<boolean> {
        await this.#attempt('Page resource cleanup failed', () => this.#dependencies.resources.cleanup());
        await this.#attempt('Page DOM cleanup failed', () => this.#dependencies.pageDom.reset());
        await this.#attempt('Page checkerboard cleanup failed', () => {
            const container = this.#dependencies.pageElements.checkerboardContainer;
            const service = container ? getOptionalCheckerboardService() : null;
            if (container && service) service.disconnect(service.getContainerId(container));
        });
        await this.#attempt('Page layout cleanup failed', () => this.#dependencies.layout.cleanup());
        await this.#attempt('Page stream cleanup failed', () => this.#dependencies.streaming.cleanup());
        await this.#attempt('Page domain cleanup failed', cleanupDomainState);
        await this.#attempt('Page collection cleanup failed', onCollectionStateCleaned);
        await this.#attempt('Page DOM cache cleanup failed', () => this.#dependencies.services.clearDomCache());
        this.#cleanupPerformed = true;
        return true;
    }
}

export { PageTeardown };
export type { PageTeardownDependencies };
