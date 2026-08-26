/* SoAI - Shared routing collection contracts [frontend/assets/ts/core/routing/pages/pagetypes/collection/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { CollectionRuntime, CollectionItem } from '@core/data/collectionview/service.ts';
import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import type { IdNormalizer, StoreItemRecord } from '@core/CollectionsStore.ts';

export interface CollectionOptionsInternal {
    normalizeId?: IdNormalizer<StoreItemRecord>;
    normalize?: (item: ResourceIncomingValue) => CollectionItem;
    fingerprint?: (item: CollectionItem, raw?: ResourceIncomingValue) => string;
}

export interface CollectionConfigurationOptions {
    collectionKey: string;
    gridId?: string;
    emptyStateId?: string;
    renderItem?: (item: CollectionItem, context?: ResourceIncomingValue) => HTMLElement | Node;
    loadingLabel?: (() => string) | undefined;
    resolveContainer?: (() => HTMLElement | null) | undefined;
    resolveItemIdentifier?: ((element: HTMLElement) => string | null) | undefined;
    collectionOptions?: CollectionOptionsInternal;
}

export interface CollapseApplyOptions {
    persist?: boolean;
    skip?: boolean;
    force?: boolean;
}

export interface CollapseControllerOptions {
    card?: Element | string;
    selector?: string;
    contentSelector?: string;
    contentElement?: Element;
    titleBarSelector?: string;
    persistKey?: string;
    key?: string;
    collapsedClass?: string;
    hiddenClass?: string;
    contentCollapsedClass?: string;
    guardSelector?: string;
    toggleButtonCollapsedClass?: string;
    toggleButtonSelector?: string;
    animate?: boolean;
    animationDuration?: number;
    animationEasing?: string;
    initialCollapsed?: boolean;
    enableKeyboard?: boolean;
    generateContentId?: boolean;
    noInitialize?: boolean;
    onCollapse?: () => void;
    onExpand?: () => void;
    onStateChange?: (collapsed: boolean) => void;
    onReady?: (collapsed: boolean) => void;
}

export interface CollapseController {
    key: string;
    element: Element;
    card: Element;
    container: Element;
    content: Element;
    titleBar: Element;
    toggleButton: Element | null;
    apply(collapsed: boolean, options?: CollapseApplyOptions): boolean;
    toggle(options?: CollapseApplyOptions): boolean;
    collapse(options?: CollapseApplyOptions): boolean;
    expand(options?: CollapseApplyOptions): boolean;
    isCollapsed(): boolean;
    refresh(): boolean;
}

export type { CollectionRuntime };

export interface CollectionTargets {
    emptyElement: Element;
    gridElement: Element;
}

export interface ReapplyCollectionOptions {
    shouldRender?: boolean;
    updateStats?: boolean;
    updateFilters?: boolean;
    resetScroll?: boolean;
}

export interface GridPosition {
    x: number;
    y: number;
    width: number;
    height: number;
}

export interface CreateSectionOptions {
    title?: string;
    subtitle?: string;
    controls?: TrustedHtml;
    className?: string;
    position?: GridPosition | null;
    showSubtitle?: boolean;
    loadingText?: string | undefined;
}
