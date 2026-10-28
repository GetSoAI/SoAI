/* SoAI - Model detail page control layer parameter view manager DOM contracts [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { drainCleanupStack } from '@core/lifecycle/cleanup.ts';
import { matchesSearchFilterQuery, normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { isArray, isInstanceOf, isObject, isString } from '@core/typeGuards.ts';
import type { ParameterValue } from '@pages/modeldetail/contracts/parameterTypes.ts';
import type { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import { CATEGORY_COUNT_SELECTOR, PARAMETER_CATEGORY_SELECTOR, PARAMETER_ITEM_SELECTOR, PARAMETERS_EMPTY_STATE_ID, PARAMETERS_INTERFACE_ID } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';
import type { BoundParameterEvents, ParameterElementCache, ParameterViewFilters, ParameterViewHost } from '@pages/modeldetail/controllers/parameterviewmanager/types.ts';
import { resolveParameterInputId } from '@pages/modeldetail/widgets/parametertemplates/state.ts';

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

const registerHandlers = (host: ParameterViewHost, container: Element, selector: string, eventName: string, boundEvents: BoundParameterEvents, eventDisposers: Array<() => void>, handler: (event: Event, target: HTMLElement) => void): void => {
    host.dom.resolveAll(selector, container).forEach((element) => {
        if (!isInstanceOf(element, HTMLElement)) {
            throw new TypeError('Parameter control element must be an HTMLElement');
        }
        const events = boundEvents.get(element) ?? new Set<string>();
        if (events.has(eventName)) {
            return;
        }
        events.add(eventName);
        boundEvents.set(element, events);
        const disposer = host.pageResources.on(element, eventName, (event: Event) => handler(event, element));
        if (typeof disposer === 'function') {
            eventDisposers.push(disposer);
        }
    });
};

const disposeEventHandlers = (eventDisposers: Array<() => void>, boundEvents: BoundParameterEvents): void => {
    drainCleanupStack(eventDisposers, (runtimeError) => {
        errorHandler.warn('ParameterViewManager', 'Parameter event cleanup failed', runtimeError);
    });
    boundEvents.clear();
};

const resolveParameterKeywords = (state: ParameterStateManager, key: string): string[] => {
    const keywords = state.getMetadata(key)?.keywords;
    if (keywords?.length) {
        return keywords;
    }
    const definition = state.getParameter(key)?.definition;
    const aliases = isArray(definition?.aliases) ? definition.aliases : [];
    return [key, definition?.displayName, definition?.description, ...aliases].map((token) => (isString(token) ? normalizeSearchMatchQuery(token) : '')).filter(Boolean);
};

const matchesParameterFilters = (host: ParameterViewHost, state: ParameterStateManager, filters: ParameterViewFilters, key: string, element: Element, isModified: (key: string) => boolean): boolean => {
    const { search, group, view } = filters;
    if (search && !resolveParameterKeywords(state, key).some((token) => matchesSearchFilterQuery(token, search))) {
        return false;
    }
    if (group !== null && (state.getMetadata(key)?.group ?? getDomData(host, element, 'group')) !== group) {
        return false;
    }
    if (view === 'customized') {
        return state.isParameterCustomized(key);
    }
    return view === 'unsaved' ? isModified(key) : true;
};

const applyFilters = (host: ParameterViewHost, state: ParameterStateManager, filters: ParameterViewFilters, elementCache: ParameterElementCache, isModified: (key: string) => boolean): Map<string, number> => {
    if (!elementCache.size) {
        refreshElementCache(host, elementCache);
    }

    let visibleParameterCount = 0;
    for (const [key, element] of elementCache.entries()) {
        if (!element.isConnected) {
            elementCache.delete(key);
            continue;
        }
        const visible = matchesParameterFilters(host, state, filters, key, element, isModified);
        host.pageDom.toggleClass(element, CSS_CLASSES.HIDDEN, !visible);
        if (visible) {
            visibleParameterCount += 1;
        }
    }

    const categoryCounts = new Map<string, number>();
    host.$$(PARAMETER_CATEGORY_SELECTOR).forEach((categoryElement) => {
        const category = getDomData(host, categoryElement, 'category');
        const count = host.$$(PARAMETER_ITEM_SELECTOR, categoryElement).reduce((total, item) => total + (item.classList.contains(CSS_CLASSES.HIDDEN) ? 0 : 1), 0);
        const badge = host.pageDom.optional(CATEGORY_COUNT_SELECTOR, categoryElement);
        if (badge) {
            host.pageDom.updateText(badge, i18n.plural('modelDetail.parameters.count', count, { count: i18n.formatNumber(count) }));
        }
        host.pageDom.toggleClass(categoryElement, CSS_CLASSES.HIDDEN, count === 0);
        if (category) {
            categoryCounts.set(category, count);
        }
    });

    const container = requireElement(host, PARAMETERS_INTERFACE_ID);
    const emptyState = host.pageDom.optional(PARAMETERS_EMPTY_STATE_ID, container);
    if (emptyState) {
        host.pageDom.toggleClass(emptyState, CSS_CLASSES.HIDDEN, visibleParameterCount > 0);
    }
    return categoryCounts;
};

const updateParameterUi = (host: ParameterViewHost, state: ParameterStateManager, parameterKey: string, value: ParameterValue, rerenderArrayInput: (key: string) => void): void => {
    const validation = host.pageDom.optional(`${resolveParameterInputId(parameterKey)}-validation`);
    if (validation) {
        host.pageDom.updateText(validation, '');
        host.pageDom.toggleClass(validation, 'error', false);
    }
    const displayValue = value ?? state.getParameter(parameterKey)?.definition?.default;
    if (isArray(displayValue)) {
        rerenderArrayInput(parameterKey);
        return;
    }
    host.$$(`${PARAMETER_ITEM_SELECTOR}[data-param="${CSS.escape(parameterKey)}"] :is(input, textarea, select)[data-param]`).forEach((input) => {
        input.setAttribute('aria-invalid', 'false');
        if (input instanceof HTMLInputElement && input.type === 'checkbox') {
            const checked = displayValue === true || displayValue === 'true';
            host.pageDom.updateProperty(input, 'checked', checked);
            updateToggleLabel(input, { checked });
            return;
        }

        if (!(input instanceof HTMLInputElement) && !(input instanceof HTMLTextAreaElement) && !(input instanceof HTMLSelectElement)) {
            throw new TypeError('Parameter control must be an HTMLInputElement, HTMLTextAreaElement, or HTMLSelectElement');
        }

        const normalized = displayValue !== null && displayValue !== undefined && isObject(displayValue) ? JSON.stringify(displayValue, null, 2) : String(displayValue ?? '');
        host.setUIValue(input, normalized, { attribute: 'value', skipChangeEvent: true });
    });
};

const validateArrayControls = (host: ParameterViewHost, parameterKey: string): boolean =>
    host.$$(`.array-item-input[data-param="${CSS.escape(parameterKey)}"]`).every((element) => {
        if (!(element instanceof HTMLInputElement)) throw new TypeError('Array parameter control must be an input');
        return element.reportValidity();
    });

export { applyFilters, disposeEventHandlers, getDomData, refreshElementCache, registerHandlers, requireElement, resolveElement, updateParameterUi, validateArrayControls };
