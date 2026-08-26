/* SoAI - Collection lifecycle dependency and operation contracts [frontend/assets/ts/core/routing/pages/collections/pagelifecyclemanager/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageCollectionsContract } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { CollectionLayoutRuntime } from '@core/routing/pages/collections/resource/service.ts';

interface LifecycleOptions {
    checkerboardSelector?: string | null | undefined;
    waitAttempts?: number | undefined;
}

interface WaitOptions {
    attempts?: number | undefined;
    signal?: AbortSignal | undefined;
    allowDiscovery?: boolean | undefined;
}

interface LayoutElements {
    grid: HTMLElement;
    emptyState: HTMLElement | null;
}

interface CollectionLifecycleDependencies {
    pageId: string;
    layout: CollectionLayoutRuntime;
    collections: PageCollectionsContract;
    pageLifecycle: Pick<PageLifecycle, 'isDestroyed' | 'signal'>;
}

export type { CollectionLifecycleDependencies, LayoutElements, LifecycleOptions, WaitOptions };
