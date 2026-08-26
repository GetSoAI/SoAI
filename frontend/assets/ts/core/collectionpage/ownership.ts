/* SoAI - Collection page composed owner contracts [frontend/assets/ts/core/collectionpage/ownership.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionView } from '@core/data/collectionview/service.ts';
import type { OperationProgressOptions, OperationProgressReporter } from '@core/operationprogress/types.ts';
import type { CollectionRuntime, CreateStandardSearchOptions, GenerateStandardHeaderOptions, LanguageService, ReapplyCollectionOptions, RunPageTaskOptions, StandardSearchResult, StreamHandleTrackerContract } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';

interface CollectionResourceOwners {
    collections: {
        readonly runtime: CollectionRuntime | null;
        readonly view: CollectionView | null;
        reapply(options?: ReapplyCollectionOptions): void;
        toggleEmptyState(showEmpty: boolean): void;
    };
    streaming: {
        tracker(pageKey?: string): StreamHandleTrackerContract;
        progressReporter(channel: HTMLElement | string, options?: OperationProgressOptions | null): OperationProgressReporter;
        runTask<T>(name: string, operation: () => Promise<T>, options?: RunPageTaskOptions<T>): Promise<T | null>;
    };
    layout: {
        generateHeader(options?: GenerateStandardHeaderOptions): TrustedHtml;
        createSearch(container: string | Element, options: CreateStandardSearchOptions): StandardSearchResult;
        queueHeaderActions(): void;
    };
    services: { ensureLanguageInitialized(): Promise<LanguageService> };
    pageElements: { enableCheckerboard(containerOrSelector: Element | string, id?: string, absoluteIndexOffset?: number): void };
}

export type { CollectionResourceOwners };
