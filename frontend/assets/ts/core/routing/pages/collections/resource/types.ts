/* SoAI - Shared routing resource contracts [frontend/assets/ts/core/routing/pages/collections/resource/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionLayout, HeaderConfig, HeaderMetadata, RawCollectionLayout, ResolvedCollectionLayout } from '@core/routing/pages/collections/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';

interface CollectionConfig {
    collectionKey?: string | undefined;
    gridId?: string | undefined;
    emptyStateId?: string | undefined;
    searchPlaceholder?: string | undefined;
}

interface WaitOptions {
    timeoutMs?: number | undefined;
    attempts?: number | undefined;
    signal?: AbortSignal | undefined;
}

interface WaitBudget {
    timeoutMs: number;
    signal: AbortSignal | null;
}

interface WithLoadingOptions<T extends JsonValue | null = JsonValue | null> {
    loadingText?: string | undefined;
    successMessage?: string | undefined;
    errorPrefix?: string | undefined;
    onSuccess?: ((result: T) => Promise<void> | void) | undefined;
    onError?: ((error: Error | null) => Promise<void> | void) | undefined;
    onFinally?: (() => Promise<void> | void) | undefined;
    rethrow?: boolean | undefined;
    taskName?: string | undefined;
    displayName?: string | undefined;
    signal?: AbortSignal | undefined;
}

interface LayoutElements {
    grid: HTMLElement;
    emptyState: HTMLElement | null;
}

interface HostInterface {
    container?: Element | null | undefined;
    isDestroyed?: boolean | undefined;
    optionalHTMLElement?: (selector: string, container?: Element) => HTMLElement | null;
    getRuntimeAbortSignal?: () => AbortSignal | null;
    collections?: {
        configuration(): { collectionKey?: string | undefined } | null;
    };
    defineCollectionLayout?: () => CollectionLayout;
    resolveHostContainer?: () => Element | null;
}

interface RouterInterface {
    navigate: (route: string, options?: Record<string, string | null>) => string | null;
}

type ModelInterface = ModelRecord;

type CollectionLayoutState = {
    value: ResolvedCollectionLayout | null;
};

export type { CollectionConfig, CollectionLayoutState, HeaderConfig, HeaderMetadata, HostInterface, LayoutElements, ModelInterface, RawCollectionLayout, ResolvedCollectionLayout, RouterInterface, WaitBudget, WaitOptions, WithLoadingOptions };
