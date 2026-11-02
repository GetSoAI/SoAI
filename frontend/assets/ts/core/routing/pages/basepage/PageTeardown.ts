/* SoAI - Routed page deterministic teardown ownership [frontend/assets/ts/core/routing/pages/basepage/PageTeardown.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { getOptionalCheckerboardService } from '@core/routing/pages/pageDom.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageCollapsibleCards } from '@core/routing/pages/basepagelayout/PageCollapsibleCards.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageDestroyCommand } from '@core/routing/pages/basepage/pageLifecycleContracts.ts';
import { createDeferred } from '@core/runtime/deferred.ts';

interface PageTeardownDependencies {
    pageId: string;
    layout: PageLayout;
    streaming: PageStreaming;
    resources: PageResources;
    pageDom: PageDom;
    pageElements: PageUi;
    collapsibleCards: PageCollapsibleCards;
}

class PageTeardown {
    readonly #dependencies: PageTeardownDependencies;
    readonly #disposalSteps = new Map<string, Promise<void>>();
    #cleanupPerformed = false;
    #cleanupTask: Promise<boolean> | null = null;
    #cleanupCallbackDepth = 0;

    constructor(dependencies: PageTeardownDependencies) {
        this.#dependencies = dependencies;
    }

    reset(): void {
        if (this.#disposalSteps.size) throw new Error('Disposed page cannot reset teardown ownership');
        this.#cleanupPerformed = false;
        this.#cleanupTask = null;
    }

    #disposeStep(label: string, operation: () => Promise<void> | void): Promise<void> {
        const existing = this.#disposalSteps.get(label);
        if (existing) return existing;
        const completion = createDeferred<void>();
        this.#disposalSteps.set(label, completion.promise);
        try {
            Promise.resolve(operation()).then(completion.resolve, (error) => completion.reject(ensureError(error)));
        } catch (error) {
            completion.reject(ensureError(error));
        }
        return completion.promise;
    }

    async destroyOwnedState(command: PageDestroyCommand): Promise<void> {
        this.#dependencies.resources.seal();
        const failures: Error[] = [];
        const steps: readonly [string, () => Promise<void> | void][] = [
            ['domain destruction', command.onDestroy],
            ['collapsible cards', () => this.#dependencies.collapsibleCards.reset()],
            ['layout destruction', () => this.#dependencies.layout.destroy()],
            ['stream destruction', () => this.#dependencies.streaming.destroy()],
            ['resource disposal', () => this.#dependencies.resources.dispose()],
            [
                'page cleanup',
                async () => {
                    await this.cleanup(command.cleanupDomainState, command.onCollectionStateCleaned);
                }
            ]
        ];
        for (const [label, operation] of steps) {
            try {
                await this.#disposeStep(label, operation);
            } catch (error) {
                failures.push(new Error(`Page ${this.#dependencies.pageId} ${label} incomplete`, { cause: ensureError(error) }));
            }
        }
        if (failures.length) throw new AggregateError(failures, `Page ${this.#dependencies.pageId} disposal incomplete`);
    }

    async cleanup(cleanupDomainState: () => void, onCollectionStateCleaned: () => void): Promise<boolean> {
        if (this.#cleanupPerformed) return false;
        if (this.#cleanupTask) return this.#cleanupCallbackDepth ? false : await this.#cleanupTask;
        const completion = createDeferred<boolean>();
        this.#cleanupTask = completion.promise;
        void this.#runCleanup(cleanupDomainState, onCollectionStateCleaned).then(completion.resolve, (error) => completion.reject(ensureError(error)));
        return await completion.promise;
    }

    async #runCleanup(cleanupDomainState: () => void, onCollectionStateCleaned: () => void): Promise<boolean> {
        const failures: Error[] = [];
        const steps: readonly [string, () => Promise<void> | void][] = [
            ['resources', () => (this.#disposalSteps.has('resource disposal') ? undefined : this.#dependencies.resources.cleanup())],
            ['DOM', () => this.#dependencies.pageDom.reset()],
            [
                'checkerboard',
                () => {
                    const container = this.#dependencies.pageElements.checkerboardContainer;
                    const service = container ? getOptionalCheckerboardService() : null;
                    if (container && service) service.disconnect(service.getContainerId(container));
                }
            ],
            ['layout', () => this.#dependencies.layout.cleanup()],
            ['streams', () => this.#dependencies.streaming.cleanup()],
            ['domain', cleanupDomainState],
            ['collection', onCollectionStateCleaned]
        ];
        for (const [label, operation] of steps) {
            try {
                this.#cleanupCallbackDepth += 1;
                let task: Promise<void> | void;
                try {
                    task = operation();
                } finally {
                    this.#cleanupCallbackDepth -= 1;
                }
                await task;
            } catch (error) {
                failures.push(new Error(`Page ${this.#dependencies.pageId} ${label} cleanup incomplete`, { cause: ensureError(error) }));
            }
        }
        if (failures.length) throw new AggregateError(failures, `Page ${this.#dependencies.pageId} cleanup incomplete`);
        this.#cleanupPerformed = true;
        return true;
    }
}

export { PageTeardown };
export type { PageTeardownDependencies };
