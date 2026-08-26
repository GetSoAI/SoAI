/* SoAI - Shared collection page contracts [frontend/assets/ts/core/collectionpage/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CollectionOptionsInternal, StreamHandle } from '@core/routing/pages/pagetypes/public.ts';
import type { ResourceIncomingValue, ResourceItem, ResourceOperation } from '@core/data/ClientDataHub.ts';

type CollectionItem = ResourceItem;

type CollectionItemInput = ResourceIncomingValue | null | undefined;

interface Collection {
    getFiltered(): CollectionItem[];
    getAll(): CollectionItem[];
}

interface CollectionView {
    applyOperations(operations: CollectionOperation[]): void;
    replaceLocal(items: CollectionItem[]): void;
    upsertLocal(item: CollectionItem): void;
    removeLocal(id: string): void;
    flushPendingRefresh(): void;
    awaitInitialCommit(signal: AbortSignal | null): Promise<boolean>;
}

type CollectionOperation = ResourceOperation;

interface StreamTracker {
    active: Map<string, StreamHandle>;
    track(key: string, stream: StreamHandle): StreamHandle;
    release(key: string, options?: { cancel?: boolean }): void;
    clear(options?: { abort?: boolean; cancel?: boolean }): void;
}

interface ProgressReporter {
    remove?(key: string): void;
    destroy(): void;
}

interface DownloadStream {
    finished: Promise<StreamResult>;
}

interface StreamResult {
    cancelled?: boolean;
    success?: boolean;
    message?: string;
}

interface Storage {
    get?(key: string): JsonValue | null;
    set?(key: string, value: JsonValue | null): void;
}

interface DeletionConfig {
    identifier: string;
    confirmTitle: string;
    confirmMessage: string;
    confirmButton: string;
    getStream(): Promise<DownloadStream>;
    gridId: string;
    findCard?(grid: HTMLElement | null, identifier: string): HTMLElement | null;
    pendingClass: string;
    successMessage: string;
}

interface CollectionConfig {
    collectionKey?: string | undefined;
    collectionOptions?: CollectionOptionsInternal | undefined;
    defaultSort?: string | undefined;
    [key: string]: JsonValue | CollectionOptionsInternal | undefined;
}

interface FilterConfig {
    filters?: Record<string, string>;
}

interface SearchConfig {
    placeholder?: string | undefined;
    onSearch?(query: string): void;
    onClear?(): void;
}

interface CollectionMutationContext {
    pageId: string;
    getCollection(): Collection | null;
    getCollectionView(): CollectionView | null;
    isValidItem(candidate: CollectionItemInput): candidate is CollectionItem;
    normalizeItem(item: CollectionItem): CollectionItem;
    getItemCardId(item: CollectionItemInput): string | null;
    clearSessionDeleted(id: string): void;
    getSessionDeletedIds(): Set<string>;
    markAsSessionDeleted(id: string): void;
}

interface CollectionTransferContext {
    getStreams(): StreamTracker;
    getProgressReporter(): ProgressReporter | null;
}

interface CollectionSearchContext {
    pageId: string;
    createStandardSearch(containerId: string, config: { placeholder: string; onSearch(query: string): void; onClear(): void; debounceTime: number }): void;
    setSearchQuery(query: string): void;
    reapplyCollection(options: { shouldRender: boolean; resetScroll: boolean }): void;
}

interface CollectionFilterContext {
    pageId: string;
    queryElements(selector: string): Element[];
    bindEvent(target: EventTarget, event: string, handler: (event: Event) => void): void;
    setFilterValue(property: string, value: string): void;
    reapplyCollection(options: { shouldRender: boolean; resetScroll: boolean }): void;
}

interface CollectionDeletionContext extends CollectionMutationContext, CollectionTransferContext {
    isDeleting(identifier: string): boolean;
    markDeleting(identifier: string): void;
    clearDeleting(identifier: string): void;
    getUiElement(selector: string): HTMLElement | null;
    showSuccess(message: string): void;
    handleError(error: Error, message: string): void;
    renderItems(): void;
}

type CollectionItemInputList = readonly CollectionItemInput[];

export type { CollectionItem, CollectionItemInput, CollectionItemInputList, Collection, CollectionView, CollectionOperation, StreamTracker, ProgressReporter, DownloadStream, StreamResult, Storage, DeletionConfig, CollectionConfig, FilterConfig, SearchConfig, CollectionMutationContext, CollectionTransferContext, CollectionSearchContext, CollectionFilterContext, CollectionDeletionContext };
