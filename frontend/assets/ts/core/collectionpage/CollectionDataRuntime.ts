/* SoAI - Collection mutation, transfer, deletion, and session state ownership [frontend/assets/ts/core/collectionpage/CollectionDataRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cancelDownloadAction, executeItemDeletionAction, removeItemByIdAction, setItemsFromListAction, upsertItemAction } from '@core/collectionpage/actions.ts';
import { readSessionDeletedIds, writeSessionDeletedIds } from '@core/collectionpage/sessionDeleted.ts';
import type { Collection, CollectionDeletionContext, CollectionItem, CollectionItemInput, CollectionItemInputList, CollectionMutationContext, CollectionOperation, DeletionConfig, ProgressReporter, Storage, StreamTracker } from '@core/collectionpage/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { PageCollectionsContract } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';

interface CollectionDataBehavior {
    isValidItem(candidate: CollectionItemInput): candidate is CollectionItem;
    normalizeItem(item: CollectionItem): CollectionItem;
    getItemCardId(item: CollectionItemInput): string | null;
    renderItems(): void;
}

interface CollectionDataDependencies {
    pageId: string;
    storage: Storage;
    collections: PageCollectionsContract;
    streaming: PageStreaming;
    pageDom: PageDom;
    feedback: PageFeedback;
    behavior: CollectionDataBehavior;
}

class CollectionDataRuntime {
    readonly #dependencies: CollectionDataDependencies;
    readonly #sessionDeletedKey: string;
    readonly #deletingItems = new Set<string>();
    #streams: StreamTracker | null = null;
    #progressReporter: ProgressReporter | null = null;

    constructor(dependencies: CollectionDataDependencies) {
        this.#dependencies = dependencies;
        this.#sessionDeletedKey = `${dependencies.pageId}_deleted`;
    }

    get streams(): StreamTracker {
        this.#streams ??= this.#dependencies.streaming.tracker(this.#dependencies.pageId);
        return this.#streams;
    }

    get progressReporter(): ProgressReporter {
        this.#progressReporter ??= this.#dependencies.streaming.progressReporter('operation-progress-list', {
            onCancel: (key: string): void => this.cancelDownload(key)
        });
        return this.#progressReporter;
    }

    setItemsFromList(items: CollectionItemInputList, options?: { emit?: true }): CollectionItem[] | null;
    setItemsFromList(items: CollectionItemInputList, options: { emit: false }): CollectionOperation[];
    setItemsFromList(items: CollectionItemInputList, options: { emit?: boolean } = {}): CollectionOperation[] | CollectionItem[] | null {
        return setItemsFromListAction(this.#mutationContext(), items, options.emit !== false);
    }

    upsertItem(item: CollectionItem, options: { emit: false }): CollectionOperation[];
    upsertItem(item: CollectionItem, options?: { emit?: true }): CollectionItem | null;
    upsertItem(item: CollectionItem, options: { emit?: boolean } = {}): CollectionOperation[] | CollectionItem | null {
        return upsertItemAction(this.#mutationContext(), item, options.emit !== false);
    }

    removeItemById(identifier: string, options: { emit?: boolean } = {}): CollectionOperation[] | boolean {
        return removeItemByIdAction(this.#mutationContext(), identifier, options.emit !== false);
    }

    cancelDownload(key: string): void {
        cancelDownloadAction({ getStreams: () => this.streams, getProgressReporter: () => this.#progressReporter }, key);
    }

    async executeItemDeletion(config: DeletionConfig): Promise<void> {
        await executeItemDeletionAction(this.#deletionContext(), config);
    }

    async safeExecute<T>(operation: () => Promise<T>, message: string): Promise<T> {
        try {
            return await operation();
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#dependencies.feedback.handle(runtimeError, message, { notify: true });
            throw runtimeError;
        }
    }

    getSessionDeletedIds(): Set<string> {
        return readSessionDeletedIds(this.#dependencies.pageId, this.#dependencies.storage, this.#sessionDeletedKey);
    }

    markAsSessionDeleted(identifier: string): void {
        if (!identifier) return;
        const deleted = this.getSessionDeletedIds();
        deleted.add(identifier);
        writeSessionDeletedIds(this.#dependencies.storage, this.#sessionDeletedKey, deleted);
    }

    clearSessionDeleted(identifier: string): void {
        if (!identifier) return;
        const deleted = this.getSessionDeletedIds();
        deleted.delete(identifier);
        writeSessionDeletedIds(this.#dependencies.storage, this.#sessionDeletedKey, deleted);
    }

    destroy(): void {
        this.#streams?.clear({ abort: true, cancel: false });
        this.#streams = null;
        this.#deletingItems.clear();
        this.#progressReporter?.destroy();
        this.#progressReporter = null;
    }

    #mutationContext(): CollectionMutationContext {
        const behavior = this.#dependencies.behavior;
        return {
            pageId: this.#dependencies.pageId,
            getCollection: (): Collection | null => this.#dependencies.collections.runtime,
            getCollectionView: () => this.#dependencies.collections.view,
            isValidItem: (candidate): candidate is CollectionItem => behavior.isValidItem(candidate),
            normalizeItem: (item) => behavior.normalizeItem(item),
            getItemCardId: (item) => behavior.getItemCardId(item),
            clearSessionDeleted: (identifier) => this.clearSessionDeleted(identifier),
            getSessionDeletedIds: () => this.getSessionDeletedIds(),
            markAsSessionDeleted: (identifier) => this.markAsSessionDeleted(identifier)
        };
    }

    #deletionContext(): CollectionDeletionContext {
        return {
            ...this.#mutationContext(),
            getStreams: () => this.streams,
            getProgressReporter: () => this.#progressReporter,
            isDeleting: (identifier) => this.#deletingItems.has(identifier),
            markDeleting: (identifier) => this.#deletingItems.add(identifier),
            clearDeleting: (identifier) => this.#deletingItems.delete(identifier),
            getUiElement: (selector) => this.#dependencies.pageDom.optionalHTMLElement(selector),
            showSuccess: (message) => this.#dependencies.feedback.success(message),
            handleError: (error, message) => this.#dependencies.feedback.handle(error, message, { notify: true }),
            renderItems: () => this.#dependencies.behavior.renderItems()
        };
    }
}

const defaultCollectionDataBehavior = {
    isValidItem: (candidate: CollectionItemInput): candidate is CollectionItem => Boolean(candidate && isObject(candidate) && (('id' in candidate && candidate['id']) || ('name' in candidate && candidate['name']))),
    normalizeItem: (item: CollectionItem): CollectionItem => item,
    getItemCardId: (item: CollectionItemInput): string | null => {
        if (!item || !isObject(item) || isArray(item)) return null;
        const identifier = item['id'] ?? item['name'];
        return isString(identifier) || typeof identifier === 'number' ? String(identifier) : null;
    }
};

export { CollectionDataRuntime, defaultCollectionDataBehavior };
export type { CollectionDataBehavior, CollectionDataDependencies };
