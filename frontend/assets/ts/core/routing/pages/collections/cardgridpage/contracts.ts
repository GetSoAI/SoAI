/* SoAI - Shared routing card grid page contracts [frontend/assets/ts/core/routing/pages/collections/cardgridpage/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';

interface CardPageHost {
    dom?:
        | {
              getData?(element: Element, key: string): string | null | undefined;
              setData?(element: Element, key: string, value: string): void;
          }
        | undefined;
    optionalUI(selector: string): Element | null;
    toggleHidden(element: Element, hidden: boolean): void;
    flushDOMUpdates(): void;
    queueResponsiveLayoutUpdate(): void;
}

interface CardWithDataset extends Element {
    dataset?: DOMStringMap | undefined;
}

interface EmptyState {
    element?: Element | null | undefined;
    selector?: string | undefined;
    visibleWhen: ((context: { filtered: (ResourceIncomingValue | null)[]; all: (ResourceIncomingValue | null)[] }) => boolean) | boolean;
}

interface CardPageConfig {
    dataKey: string;
    getItemId: (item: ResourceIncomingValue | null | undefined) => string | null;
    resolveCurrentItem?: ((identifier: string) => ResourceIncomingValue | null) | undefined;
    itemLabel?: string | undefined;
    collectionName?: string | undefined;
    cardSelector?: string | null | undefined;
    gridSelector?: string | null | undefined;
    emptyStates?: EmptyState[] | null | undefined;
    cacheKey?: string | undefined;
    loadingText?: string | undefined;
}

interface RenderOptions {
    filteredItems?: (ResourceIncomingValue | null)[] | undefined;
    allItems?: (ResourceIncomingValue | null)[] | undefined;
    emptyStates?: EmptyState[] | null | undefined;
}

interface CardPageController {
    cardIndex: Map<string, ResourceIncomingValue | null>;
    getItemFromCard(card: Element): ResourceIncomingValue | null | undefined;
    renderCollection(options?: RenderOptions): void;
    syncIndex(items: (ResourceIncomingValue | null)[]): void;
    setDataInitialized(): void;
    showLoading(): void;
    hideLoading(): void;
    isLoading(): boolean;
    dispose(): void;
}

export type { CardPageConfig, CardPageController, CardPageHost, CardWithDataset, EmptyState, RenderOptions };
