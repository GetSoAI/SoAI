/* SoAI - Shared DOM actions validation [frontend/assets/ts/core/dom/actions/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isArray, isBoolean, isNullOrUndefined, isPlainObject, isString } from '@core/typeGuards.ts';
import { isTrustedHtml } from '@core/security/public.ts';

import type { ElementOptions, ElementOptionValue } from '@core/dom/types.ts';
import type { DomApi } from '@core/dom/actions/types.ts';

const parseClassTokens = (value: ElementOptionValue): string[] => {
    if (isString(value)) {
        return value
            .split(/\s+/)
            .map((token) => token.trim())
            .filter(Boolean);
    }
    if (isArray(value)) {
        return value.flatMap(parseClassTokens);
    }
    return [];
};

const isElementPropertyValue = (value: ElementOptionValue): value is string | number | boolean => isString(value) || typeof value === 'number' || isBoolean(value);

const applyElementOptions = (element: Element, options: ElementOptions = {}, dom: DomApi, { preferAttributes = false }: { preferAttributes?: boolean } = {}): void => {
    const props: Record<string, ElementOptionValue> = isPlainObject(options) ? { ...options } : {};
    const includeIdClass = props['includeIdClass'] !== false;
    delete props['includeIdClass'];

    if ('title' in props && !isNullOrUndefined(props['title'])) {
        throw new Error('ElementOptions.title is forbidden. Use data-tooltip via setTooltipText().');
    }

    if ('id' in props && !isNullOrUndefined(props['id'])) {
        if (!isString(props['id']) || !toTrimmedString(props['id'])) {
            throw new Error('ElementOptions.id must be a non-empty string');
        }
    }

    const classNameTokens = parseClassTokens(props['className']);
    const classTokens = parseClassTokens(props['class']);
    delete props['class'];

    const mergedClasses = [...classNameTokens, ...classTokens];
    if (includeIdClass && isString(props['id']) && toTrimmedString(props['id'])) {
        mergedClasses.push(toTrimmedString(props['id']));
    }
    if (mergedClasses.length > 0) {
        props['className'] = mergedClasses;
    }

    for (const [key, value] of Object.entries(props)) {
        if (isNullOrUndefined(value)) continue;

        if (key === 'className') {
            const tokens = parseClassTokens(value);
            if (tokens.length > 0) dom.addClass(element, tokens);
            continue;
        }

        if (key === 'textContent') {
            if (!isElementPropertyValue(value)) {
                throw new Error('ElementOptions.textContent must be a primitive value');
            }
            dom.setText(element, value);
            continue;
        }

        if (key === 'html') {
            if (!isTrustedHtml(value)) throw new Error('ElementOptions.html must be a TrustedHtml value');
            dom.setHTML(element, value, { escape: false });
            continue;
        }

        if (key === 'style') {
            if (!isPlainObject(value)) throw new Error('ElementOptions.style must be an object map');
            const styles: Record<string, string | null> = {};
            for (const [styleProperty, styleValue] of Object.entries(value)) {
                if (isNullOrUndefined(styleValue)) {
                    styles[styleProperty] = null;
                    continue;
                }
                if (!isString(styleValue)) {
                    throw new Error(`ElementOptions.style.${styleProperty} must be a string`);
                }
                styles[styleProperty] = styleValue;
            }
            dom.setStyles(element, styles);
            continue;
        }

        if (key === 'dataset') {
            if (!isPlainObject(value)) throw new Error('ElementOptions.dataset must be an object map');
            for (const [datasetKey, datasetValue] of Object.entries(value)) {
                if (isNullOrUndefined(datasetValue)) continue;
                if (!isString(datasetValue)) {
                    throw new Error(`ElementOptions.dataset.${datasetKey} must be a string`);
                }
                dom.setData(element, datasetKey, datasetValue);
            }
            continue;
        }

        if (!preferAttributes && key in element) {
            if (!isElementPropertyValue(value)) {
                throw new Error(`ElementOptions property ${key} must be a primitive value`);
            }
            dom.setProperties(element, { [key]: value });
            continue;
        }

        if (isBoolean(value)) {
            dom.setAttribute(element, key, value ? '' : null);
            continue;
        }

        if (typeof value === 'object' || typeof value === 'function') {
            throw new Error(`ElementOptions attribute ${key} must be a primitive value`);
        }

        dom.setAttribute(element, key, String(value));
    }

    dom.flush();
};

const createElement = (tagName: keyof HTMLElementTagNameMap | string, getDomDocument: () => Document): HTMLElement => {
    const name = isString(tagName) && toTrimmedString(tagName) ? toTrimmedString(tagName) : '';
    if (!name) {
        throw new Error('create requires a valid tagName');
    }
    return getDomDocument().createElement(name);
};

export { applyElementOptions, createElement };
