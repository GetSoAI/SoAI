/* SoAI - Shared search results renderer [frontend/assets/ts/core/search/SearchResultsRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { EMPTY_UI_HTML, uiHtml } from '@core/security/uiHtml.ts';
import { securityApi, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { isFunction, isNullOrUndefined } from '@core/typeGuards.ts';
import { SEARCH_RESULT_DATASET_ATTRIBUTES, buildSearchResultDataset } from '@core/search/searchResultActivation.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';

interface RenderContext {
    getCategoryDisplayName(category: string): string;
    getItemStatus(item: SearchItem): TrustedHtml;
    getItemIcon(item: SearchItem): TrustedHtml;
    getItemAction(item: SearchItem): string;
    itemClassName?: string | undefined;
    descriptionCharacterLimit?: number | undefined;
    includeNameAfterBadge?: boolean | undefined;
}

interface ItemContext {
    getItemStatus(item: SearchItem): TrustedHtml;
    getItemIcon(item: SearchItem): TrustedHtml;
    getItemAction(item: SearchItem): string;
    itemClassName: string;
    descriptionCharacterLimit: number | null;
    includeNameAfterBadge: boolean;
}

const trimValue = toTrimmedString;

const resolveItemClassName = (itemClassName: string | undefined): string => {
    const normalized = trimValue(itemClassName);
    return normalized ? ` ${securityApi.escapeAttribute(normalized)}` : '';
};

const resolveDescriptionCharacterLimit = (value: number | undefined): number | null => {
    if (value === undefined) {
        return null;
    }
    if (!Number.isInteger(value) || value <= 0) {
        throw new Error('SearchResultsRenderer descriptionCharacterLimit must be a positive integer');
    }
    return value;
};

const renderDescription = (description: string, limit: number | null): TrustedHtml => {
    if (limit === null || description.length <= limit) {
        return uiHtml`${description}`;
    }
    return uiHtml`${description.substring(0, limit)}...`;
};

const buildDataAttributes = (item: SearchItem | null | undefined): string => {
    if (!item) {
        throw new Error('SearchResultsRenderer item must be present');
    }
    const dataset = buildSearchResultDataset(item);
    const descriptors = [
        { attribute: SEARCH_RESULT_DATASET_ATTRIBUTES[0]?.attribute ?? 'data-type', value: dataset.type },
        { attribute: SEARCH_RESULT_DATASET_ATTRIBUTES[1]?.attribute ?? 'data-id', value: dataset.id },
        { attribute: SEARCH_RESULT_DATASET_ATTRIBUTES[2]?.attribute ?? 'data-plugin', value: dataset.plugin },
        { attribute: SEARCH_RESULT_DATASET_ATTRIBUTES[3]?.attribute ?? 'data-component', value: dataset.component },
        { attribute: SEARCH_RESULT_DATASET_ATTRIBUTES[4]?.attribute ?? 'data-gpu-index', value: dataset.gpuIndex },
        { attribute: SEARCH_RESULT_DATASET_ATTRIBUTES[5]?.attribute ?? 'data-identifier', value: dataset.identifier },
        { attribute: SEARCH_RESULT_DATASET_ATTRIBUTES[6]?.attribute ?? 'data-metric', value: dataset.metric },
        { attribute: SEARCH_RESULT_DATASET_ATTRIBUTES[7]?.attribute ?? 'data-file-path', value: dataset.filePath },
        { attribute: SEARCH_RESULT_DATASET_ATTRIBUTES[8]?.attribute ?? 'data-file-entry-type', value: dataset.fileEntryType },
        { attribute: SEARCH_RESULT_DATASET_ATTRIBUTES[9]?.attribute ?? 'data-config-path', value: dataset.configPath }
    ];
    return descriptors
        .reduce((attributes: string[], descriptor) => {
            if (descriptor.value) {
                attributes.push(`${descriptor.attribute}="${securityApi.escapeAttribute(descriptor.value)}"`);
            }
            return attributes;
        }, [])
        .join(' ');
};

const buildItemMarkup = (item: SearchItem, context: ItemContext): TrustedHtml => {
    const getItemStatus = context.getItemStatus;
    const getItemIcon = context.getItemIcon;
    const status = getItemStatus(item);
    const icon = getItemIcon(item);
    const rawBadge = trimValue(item?.badge);
    const badge = rawBadge ? uiHtml`<span class="search-item-badge">${rawBadge}</span>` : EMPTY_UI_HTML;
    const rawName = trimValue(item?.name);
    if (!rawName) {
        throw new Error('SearchResultsRenderer item name must be non-empty');
    }
    const rawTitle = rawName;
    const titleText = rawTitle;
    const includeTitle = context.includeNameAfterBadge || !rawBadge || !rawTitle || rawTitle.toLowerCase() !== rawBadge.toLowerCase();
    const titleMarkup = includeTitle && titleText ? uiHtml`${badge}${rawBadge ? ' ' : ''}${titleText}` : badge;
    const description = isNullOrUndefined(item?.description) ? '' : item.description;
    const attributes = buildDataAttributes(item);
    const titleAttr = rawTitle ? `data-tooltip="${securityApi.escapeAttribute(rawTitle)}"` : '';
    const descAttr = item?.description ? `data-tooltip="${securityApi.escapeAttribute(item.description)}"` : '';
    const accessibleContext = trimValue(item.accessibleContext);
    const buttonLabel = accessibleContext ? `${rawName}, ${accessibleContext}` : rawName;
    const iconToneClass = item.iconTone === 'messaging' ? ' search-item-icon--messaging' : '';
    const action = trimValue(context.getItemAction(item));
    if (!action) {
        throw new Error('SearchResultsRenderer item action must be non-empty');
    }

    return toTrustedUiHtml(`<button type="button" class="search-item${context.itemClassName}" data-action="${securityApi.escapeAttribute(action)}" aria-label="${securityApi.escapeAttribute(buttonLabel)}" data-tooltip="${securityApi.escapeAttribute(buttonLabel)}" ${attributes}>` + `<div class="search-item-icon${iconToneClass}">${icon.html}</div>` + `<div class="search-item-content">` + `<div class="search-item-title" ${titleAttr}>${titleMarkup.html}</div>` + `<div class="search-item-description" ${descAttr}>${renderDescription(description, context.descriptionCharacterLimit).html}</div>` + `</div>` + `<div class="search-item-status">${status.html}</div>` + `</button>`);
};

const createMarkup = (results: ReadonlyArray<SearchItem>, context: RenderContext): TrustedHtml => {
    if (!Array.isArray(results)) {
        throw new Error('SearchResultsRenderer requires an array of results');
    }
    const items = results;
    if (items.length === 0) {
        return EMPTY_UI_HTML;
    }
    const getCategoryDisplayName = context.getCategoryDisplayName;
    if (!isFunction(getCategoryDisplayName)) {
        throw new Error('SearchResultsRenderer requires getCategoryDisplayName');
    }
    const getItemIcon = context.getItemIcon;
    if (!isFunction(getItemIcon)) {
        throw new Error('SearchResultsRenderer requires getItemIcon');
    }
    const getItemAction = context.getItemAction;
    if (!isFunction(getItemAction)) {
        throw new Error('SearchResultsRenderer requires getItemAction');
    }
    const getItemStatus = context.getItemStatus;
    if (!isFunction(getItemStatus)) {
        throw new Error('SearchResultsRenderer requires getItemStatus');
    }
    const itemClassName = resolveItemClassName(context.itemClassName);
    const descriptionCharacterLimit = resolveDescriptionCharacterLimit(context.descriptionCharacterLimit);
    const includeNameAfterBadge = context.includeNameAfterBadge === true;
    const grouped: Record<string, SearchItem[]> = items.reduce((acc: Record<string, SearchItem[]>, item) => {
        const key = trimValue(item?.type);
        if (!key) {
            throw new Error('SearchResultsRenderer item type must be non-empty');
        }
        if (!acc[key]) {
            acc[key] = [];
        }
        acc[key].push(item);
        return acc;
    }, {});
    const sections: string[] = [];
    for (const [category, groupItems] of Object.entries(grouped)) {
        const header = getCategoryDisplayName(category);
        sections.push(uiHtml`<div class="search-category glass-surface-strong"><div class="section-header"><h2 class="section-title">${header}</h2></div><div class="search-category-content">`.html);
        groupItems.forEach((item) => {
            sections.push(
                buildItemMarkup(item, {
                    getItemAction,
                    getItemStatus,
                    getItemIcon,
                    itemClassName,
                    descriptionCharacterLimit,
                    includeNameAfterBadge
                }).html
            );
        });
        sections.push('</div></div>');
    }
    return toTrustedUiHtml(sections.join(''));
};

const renderer = Object.freeze({
    createMarkup
});

export { createMarkup, renderer };
