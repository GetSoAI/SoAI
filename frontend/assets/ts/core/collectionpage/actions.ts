/* SoAI - Shared collection page actions [frontend/assets/ts/core/collectionpage/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { isArray, isFunction, isInstanceOf, isString } from '@core/typeGuards.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { findCollectionItemById, normalizeIncomingItems, removePendingStyle, resolveDeleteSuccessMessage, resolveFilterBindings, resolveFilterTargets } from '@core/collectionpage/guards.ts';
import type { CollectionDeletionContext, CollectionFilterContext, CollectionItem, CollectionItemInputList, CollectionMutationContext, CollectionOperation, CollectionSearchContext, CollectionTransferContext, DeletionConfig, FilterConfig, SearchConfig } from '@core/collectionpage/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { IN_PLACE_SEARCH_DEBOUNCE_MS } from '@core/search/searchDebounce.ts';

export const setItemsFromListAction = (context: CollectionMutationContext, items: CollectionItemInputList, emit: boolean): CollectionOperation[] | CollectionItem[] | null => {
    if (!isArray(items)) {
        return emit ? null : [];
    }

    const normalizedList = normalizeIncomingItems(context, items);
    if (emit === false) {
        return [{ type: 'replace', items: normalizedList }];
    }

    context.getCollectionView()?.replaceLocal(normalizedList);
    return normalizedList;
};

export const upsertItemAction = (context: CollectionMutationContext, item: CollectionItem, emit: boolean): CollectionOperation[] | CollectionItem | null => {
    const normalized = context.normalizeItem(item);
    const identifier = context.getItemCardId(normalized);
    if (!identifier) {
        return emit === false ? [] : null;
    }

    if (context.getSessionDeletedIds().has(identifier)) {
        context.clearSessionDeleted(identifier);
    }

    if (emit === false) {
        return [{ type: 'upsert', item: normalized }];
    }

    context.getCollectionView()?.upsertLocal(normalized);
    return normalized;
};

export const removeItemByIdAction = (context: CollectionMutationContext, identifier: string, emit: boolean): CollectionOperation[] | boolean => {
    if (!identifier) {
        return emit === false ? [] : false;
    }

    const collection = context.getCollection();
    if (!collection?.getAll) {
        throw new Error('CollectionPage requires collection.getAll method');
    }

    const items = collection.getAll();
    if (!isArray(items)) {
        throw new Error('collection.getAll must return an array');
    }

    const matchedItem = findCollectionItemById(context, items, identifier);
    if (!matchedItem) {
        return emit === false ? [] : false;
    }

    const cardId = context.getItemCardId(matchedItem);
    if (cardId) {
        context.markAsSessionDeleted(cardId);
    }

    if (emit === false) {
        const operation: CollectionOperation = { type: 'remove' };
        if (cardId) {
            operation.id = cardId;
        }
        return [operation];
    }

    if (cardId) {
        context.getCollectionView()?.removeLocal(cardId);
    }
    return true;
};

export const cancelDownloadAction = (context: CollectionTransferContext, key: string): void => {
    if (!key) {
        return;
    }
    const streams = context.getStreams();
    if (streams.active.has(key)) {
        streams.release(key);
    }
    context.getProgressReporter()?.remove?.(key);
};

export const setupStandardSearchAction = (context: CollectionSearchContext, containerId: string | null, config: SearchConfig): void => {
    const targetId = containerId || `${context.pageId}-search-container`;
    const placeholder = isString(config.placeholder) && config.placeholder.trim() ? config.placeholder.trim() : i18n.t('header.search.placeholder');
    context.createStandardSearch(targetId, {
        placeholder,
        debounceTime: IN_PLACE_SEARCH_DEBOUNCE_MS,
        onSearch: (query: string): void => {
            context.setSearchQuery(query);
            context.reapplyCollection({ shouldRender: true, resetScroll: true });
        },
        onClear: (): void => {
            context.setSearchQuery('');
            context.reapplyCollection({ shouldRender: true, resetScroll: true });
        }
    });
};

export const setupStandardFiltersAction = (context: CollectionFilterContext, filterConfig: FilterConfig): void => {
    const filters = resolveFilterBindings(filterConfig);
    Object.entries(filters).forEach(([selector, prop]) => {
        const targets = resolveFilterTargets(context, selector);
        if (!targets.length) {
            throw new Error(`CollectionPage missing filter element ${selector}`);
        }
        targets.forEach((target) => {
            context.bindEvent(target, 'change', (event: Event): void => {
                const eventTarget = event.target;
                if (!isInstanceOf(eventTarget, HTMLSelectElement)) {
                    throw new TypeError(`CollectionPage filter change target must be an HTMLSelectElement (${selector})`);
                }
                context.setFilterValue(prop, eventTarget.value);
                context.reapplyCollection({ shouldRender: true, resetScroll: true });
            });
        });
    });
};

export const executeItemDeletionAction = async (context: CollectionDeletionContext, config: DeletionConfig): Promise<void> => {
    const { identifier, confirmTitle, confirmMessage, confirmButton, getStream, gridId, findCard, pendingClass, successMessage } = config;

    if (!identifier || context.isDeleting(identifier)) {
        return;
    }

    const cancelLabel = i18n.t('common.cancel');
    if (!isString(cancelLabel) || !cancelLabel) {
        throw new Error('Missing common.cancel translation');
    }

    const confirmed = await requireDialogsService().showConfirmation({
        title: confirmTitle,
        message: confirmMessage,
        confirmText: confirmButton,
        cancelText: cancelLabel
    });
    if (!confirmed) {
        return;
    }

    const grid = context.getUiElement(gridId);
    const card = findCard?.(grid, identifier) ?? null;
    if (card) {
        dom.addClass(card, pendingClass);
    }

    context.markDeleting(identifier);

    try {
        const stream = await getStream();
        if (!stream || !isFunction(stream.finished?.then)) {
            throw new Error('Deletion stream did not provide a valid handle');
        }

        const streams = context.getStreams();
        streams.track(identifier, stream);
        const result = await stream.finished;
        if (result?.cancelled) {
            if (card) {
                removePendingStyle(card, pendingClass);
                dom.flush();
            }
            return;
        }

        if (result?.success === false) {
            throw new Error(resolveDeleteSuccessMessage(result, successMessage));
        }

        if (result?.success) {
            removeItemByIdAction(context, identifier, true);
            card?.remove();
        }
        context.showSuccess(resolveDeleteSuccessMessage(result, successMessage));
    } catch (error) {
        const runtimeError = ensureError(error);
        context.handleError(runtimeError, 'Failed to delete item');
        removePendingStyle(card, pendingClass);
        context.renderItems();
    } finally {
        const streams = context.getStreams();
        streams.release(identifier);
        context.clearDeleting(identifier);
    }
};
