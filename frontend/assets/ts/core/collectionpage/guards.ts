/* SoAI - Shared collection page validation [frontend/assets/ts/core/collectionpage/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isString } from '@core/typeGuards.ts';
import type { CollectionFilterContext, CollectionItem, CollectionItemInputList, CollectionMutationContext, FilterConfig, StreamResult } from '@core/collectionpage/types.ts';

const normalizeIncomingItems = (context: CollectionMutationContext, items: CollectionItemInputList): CollectionItem[] => {
    const normalizedList: CollectionItem[] = [];
    for (const item of items) {
        if (!context.isValidItem(item)) {
            throw new TypeError(`${context.pageId} setItemsFromList() received an invalid item`);
        }
        const normalized = context.normalizeItem(item);
        const id = context.getItemCardId(normalized);
        if (id) {
            context.clearSessionDeleted(id);
            normalizedList.push(normalized);
        }
    }
    return normalizedList;
};

const findCollectionItemById = (context: CollectionMutationContext, items: CollectionItem[], identifier: string): CollectionItem | null => {
    for (const item of items) {
        const cardId = context.getItemCardId(item);
        if (cardId === identifier || item.id === identifier || item.name === identifier) {
            return item;
        }
    }
    return null;
};

const resolveFilterTargets = (context: CollectionFilterContext, selector: string): Element[] => context.queryElements(selector);

const resolveDeleteSuccessMessage = (result: StreamResult, successMessage: string): string => {
    if (isString(result.message) && result.message.length > 0) {
        return result.message;
    }
    return successMessage;
};

const resolveFilterBindings = (filterConfig: FilterConfig): Record<string, string> => {
    const configuredFilters = filterConfig.filters;
    if (configuredFilters) {
        return configuredFilters;
    }
    return {
        '#provider-filter': 'filterProvider',
        '#status-filter': 'filterStatus'
    };
};

const removePendingStyle = (card: HTMLElement | null, pendingClass: string): void => {
    if (!card) {
        return;
    }
    dom.removeClass(card, pendingClass);
};

export { normalizeIncomingItems, findCollectionItemById, resolveFilterTargets, resolveDeleteSuccessMessage, resolveFilterBindings, removePendingStyle };
