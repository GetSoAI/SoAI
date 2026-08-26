/* SoAI - Model detail page control layer parameter view manager DOM contracts [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceSelectOptions } from '@core/dom/selectOptions.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { drainCleanupStack } from '@core/lifecycle/cleanup.ts';
import { syncPageControlSelectValue } from '@core/pagecontrols/selectController.ts';
import { matchesSearchFilterQuery, normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import { isArray, isInstanceOf, isObject, isString } from '@core/typeGuards.ts';
import { resolveParameterCategoryLabel } from '@pages/modeldetail/contracts/parameterCategoryMetadata.ts';
import type { ParameterValue } from '@pages/modeldetail/contracts/parameterTypes.ts';
import type { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import { CATEGORY_COUNT_SELECTOR, CATEGORY_PARAMETER_ITEM_SELECTOR, PARAMETER_CATEGORY_SELECTOR, PARAMETER_ITEM_SELECTOR, PARAMETERS_EMPTY_STATE_ID, PARAMETERS_FILTER_ID, PARAMETERS_INTERFACE_ID, PARAMETERS_LAYOUT_SELECTOR } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';
import { persistModelDetailParameterFilter, readModelDetailParameterFilter } from '@pages/modeldetail/controllers/parameterviewmanager/parameterViewControlsManager.ts';
import type { ParameterElementCache, ParameterViewFilters, ParameterViewHost } from '@pages/modeldetail/controllers/parameterviewmanager/types.ts';
import { PARAMETER_COUNT_BADGE_TONE_CLASSES, resolveParameterCountBadgeTone } from '@pages/modeldetail/rendering/parameterCountBadgeTone.ts';

const requireElement = (host: ParameterViewHost, selector: string): Element => {
    const element = host.pageDom.optional(selector);
    if (!element) {
        throw new Error(`ModelDetailPage required element is missing: #${selector}`);
    }
    return element;
};

const getDomData = (host: ParameterViewHost, element: Element, key: string): string | null => {
    const value = host.dom.getData(element, key);
    return typeof value === 'string' && value.length ? value : null;
};

const refreshElementCache = (host: ParameterViewHost, elementCache: ParameterElementCache): void => {
    elementCache.clear();
    const items = host.$$(PARAMETER_ITEM_SELECTOR);
    items.forEach((element) => {
        const key = getDomData(host, element, 'param');
        if (key) {
            elementCache.set(key, element);
        }
    });
};

const resolveElement = (host: ParameterViewHost, elementCache: ParameterElementCache, parameterKey: string): Element | null => {
    const cached = elementCache.get(parameterKey);
    if (cached?.isConnected) {
        return cached;
    }
    const resolved = host.$(`${PARAMETER_ITEM_SELECTOR}[data-param="${CSS.escape(parameterKey)}"]`);
    if (resolved) {
        elementCache.set(parameterKey, resolved);
    } else {
        elementCache.delete(parameterKey);
    }
    return resolved;
};

const registerHandlers = (host: ParameterViewHost, container: Element, selector: string, eventName: string, boundElements: Set<Element>, eventDisposers: Array<() => void>, handler: (event: Event, target: HTMLElement) => void): void => {
    host.dom.resolveAll(selector, container).forEach((element) => {
        if (!isInstanceOf(element, HTMLElement)) {
            throw new TypeError('Parameter control element must be an HTMLElement');
        }
        if (boundElements.has(element)) {
            return;
        }
        boundElements.add(element);
        const disposer = host.pageResources.on(element, eventName, (event: Event) => handler(event, element));
        if (typeof disposer === 'function') {
            eventDisposers.push(disposer);
        }
    });
};

const disposeEventHandlers = (eventDisposers: Array<() => void>, boundElements: Set<Element>): void => {
    drainCleanupStack(eventDisposers, (runtimeError) => {
        errorHandler.warn('ParameterViewManager', 'Parameter event cleanup failed', runtimeError);
    });
    boundElements.clear();
};

const isBackendDocumentationSection = (element: Element): boolean => {
    return element.classList.contains('parameter-category--backend-doc');
};

const applyFilters = (host: ParameterViewHost, state: ParameterStateManager, filters: ParameterViewFilters, elementCache: ParameterElementCache): void => {
    const { search, category, group } = filters;
    if (!elementCache.size) {
        refreshElementCache(host, elementCache);
    }

    let visibleParameterCount = 0;
    for (const [key, element] of elementCache.entries()) {
        if (!element.isConnected) {
            elementCache.delete(key);
            continue;
        }

        const parameter = state.getParameter(key);
        const meta = state.getMetadata(key);
        let keywords = meta?.keywords;
        if (!keywords?.length) {
            const definition = parameter?.definition;
            const aliases = isArray(definition?.aliases) ? definition.aliases : [];
            keywords = [key, definition?.displayName, definition?.description, ...aliases].map((token) => (isString(token) ? normalizeSearchMatchQuery(token) : '')).filter(Boolean);
        }

        const matchesSearch = !search || keywords.some((token) => matchesSearchFilterQuery(token, search));
        const metaCategory = meta?.category ?? getDomData(host, element, 'category');
        const metaGroup = meta?.group ?? getDomData(host, element, 'group');
        const matchesCategory = category === 'all' || metaCategory === category;
        const matchesGroup = group === 'all' || metaGroup === group;
        const visible = matchesSearch && matchesCategory && matchesGroup;
        host.pageDom.toggleClass(element, 'u-hidden', !visible);
        if (visible) {
            visibleParameterCount += 1;
        }
    }

    host.$$(PARAMETER_CATEGORY_SELECTOR).forEach((categoryElement) => {
        if (isBackendDocumentationSection(categoryElement)) {
            host.pageDom.toggleClass(categoryElement, 'u-hidden', false);
            return;
        }
        const items = host.$$(CATEGORY_PARAMETER_ITEM_SELECTOR, categoryElement).filter((item): item is HTMLElement => isInstanceOf(item, HTMLElement));
        const count = items.reduce((total, item) => total + (item.classList.contains('u-hidden') ? 0 : 1), 0);
        const badge = host.pageDom.optional(CATEGORY_COUNT_SELECTOR, categoryElement);
        if (badge) {
            const badgeText = i18n.t('modelDetail.parameters.countLabel', { count });
            const toneClass = resolveParameterCountBadgeTone(count);
            host.pageDom.updateText(badge, badgeText);
            PARAMETER_COUNT_BADGE_TONE_CLASSES.forEach((className) => {
                host.pageDom.toggleClass(badge, className, className === toneClass);
            });
        }
        host.pageDom.toggleClass(categoryElement, 'u-hidden', count === 0);
    });

    const filterActive = Boolean(search || category !== 'all' || group !== 'all');
    const container = requireElement(host, PARAMETERS_INTERFACE_ID);
    const layout = host.pageDom.optional(PARAMETERS_LAYOUT_SELECTOR, container);
    const emptyState = host.pageDom.optional(PARAMETERS_EMPTY_STATE_ID, container);
    const showEmpty = filterActive && visibleParameterCount === 0;
    if (layout) {
        host.pageDom.toggleClass(layout, 'u-hidden', false);
    }
    if (emptyState) {
        host.pageDom.toggleClass(emptyState, 'u-hidden', !showEmpty);
    }
};

const populateFilterOptions = (host: ParameterViewHost, state: ParameterStateManager): string => {
    const selectResolved = host.pageDom.optional(PARAMETERS_FILTER_ID);
    if (!selectResolved) {
        throw new Error('ModelDetailPage required filter element is missing: #param-unified-filter');
    }
    if (!(selectResolved instanceof HTMLSelectElement)) {
        throw new TypeError('ModelDetailPage filter element #param-unified-filter must be an HTMLSelectElement');
    }
    const select = selectResolved;
    const categories = state.categories;
    if (!isObject(categories) || !Object.keys(categories).length) {
        if (readModelDetailParameterFilter(host.storage) !== 'all') persistModelDetailParameterFilter(host.storage, 'all');
        return 'all';
    }
    const options = [
        { value: 'all', label: i18n.t('modelDetail.filters.allParameters') },
        { value: 'group:startup', label: i18n.t('modelDetail.filters.groupStartup') },
        { value: 'group:inference', label: i18n.t('modelDetail.filters.groupInference') },
        ...Object.entries(categories).map(([key, value]) => ({
            value: `category:${key}`,
            label: `${i18n.t('modelDetail.filters.category')} ${resolveParameterCategoryLabel(value, key)}`
        }))
    ];
    replaceSelectOptions(
        select,
        options.map((option) => ({
            value: option.value,
            label: option.label,
            selected: option.value === select.value
        }))
    );
    const selection = syncPageControlSelectValue(
        select,
        readModelDetailParameterFilter(host.storage),
        options.map((option) => option.value),
        'all'
    );
    if (selection.requestedValue !== selection.visibleValue) persistModelDetailParameterFilter(host.storage, selection.visibleValue);
    return selection.visibleValue;
};

const updateParameterUi = (host: ParameterViewHost, state: ParameterStateManager, parameterKey: string, value: ParameterValue, rerenderArrayInput: (key: string) => void): void => {
    const displayValue = value ?? state.getParameter(parameterKey)?.definition?.default;
    if (isArray(displayValue)) {
        rerenderArrayInput(parameterKey);
        return;
    }
    host.$$(`${PARAMETER_ITEM_SELECTOR}[data-param="${CSS.escape(parameterKey)}"] [data-param]`).forEach((input) => {
        if (input instanceof HTMLInputElement && input.type === 'checkbox') {
            const checked = displayValue === true || displayValue === 'true';
            host.pageDom.updateProperty(input, 'checked', checked);
            const label = host.pageDom.optional('.toggle-label', input.closest('.toggle-switch') ?? undefined);
            if (label) {
                host.pageDom.updateText(label, checked ? i18n.t('common.boolean.true') : i18n.t('common.boolean.false'));
            }
            return;
        }

        if (!(input instanceof HTMLInputElement) && !(input instanceof HTMLTextAreaElement)) {
            throw new TypeError('Parameter control must be an HTMLInputElement or HTMLTextAreaElement');
        }

        const normalized = displayValue !== null && displayValue !== undefined && isObject(displayValue) ? JSON.stringify(displayValue, null, 2) : String(displayValue ?? '');
        host.setUIValue(input, normalized, { attribute: 'value' });
    });
};

export { applyFilters, disposeEventHandlers, getDomData, populateFilterOptions, refreshElementCache, registerHandlers, requireElement, resolveElement, updateParameterUi };
