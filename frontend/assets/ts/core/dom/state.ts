/* SoAI - Shared DOM state [frontend/assets/ts/core/dom/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { getDomDocument, getDomWindow } from '@core/dom/domEnvironment.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { isElementNode, isFunction, isHTMLElement } from '@core/typeGuards.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { ScrollStateEntry } from '@core/dom/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getCspNonce } from '@core/security/cspNonce.ts';

interface StyleState {
    className: string;
    value: string;
}

const STYLE_NAMESPACE = 'soai-style';
const dynamicStyleRuleCache = new Map<string, string>();
const elementStyleState = new WeakMap<Element, Map<string, StyleState>>();
let dynamicStyleSheet: CSSStyleSheet | null = null;
let dynamicStyleElement: HTMLStyleElement | null = null;

const toNormalizedCssValue = (value: string | null): string => toTrimmedString(value);

const normalizeCssPropertyName = (property: string): string | null => {
    const raw = toNormalizedCssValue(property);
    if (!raw) return null;
    if (raw.startsWith('--')) return raw;
    if (raw.includes('-')) return raw.toLowerCase();
    return raw
        .replace(/([A-Z])/g, '-$1')
        .toLowerCase()
        .replace(/^-/, '');
};

const sanitizeCssValue = (value: string | null): string | null => {
    const raw = toNormalizedCssValue(value);
    if (!raw) return null;
    return raw.replace(/[\n\r]+/g, ' ');
};

const ensureDynamicStyleSheet = (): CSSStyleSheet | null => {
    if (dynamicStyleSheet) return dynamicStyleSheet;

    const doc = getDomDocument();
    const sheets = Array.from(doc?.styleSheets ?? []);
    for (const sheet of sheets) {
        try {
            if (!isFunction(sheet.insertRule)) continue;
            const index = sheet.cssRules?.length ?? 0;
            sheet.insertRule(':where(:root) {}', index);
            sheet.deleteRule(index);
            dynamicStyleSheet = sheet;
            return dynamicStyleSheet;
        } catch (error) {
            ensureError(error);
            continue;
        }
    }

    if (!doc?.head || dynamicStyleElement) {
        return dynamicStyleSheet;
    }

    try {
        dynamicStyleElement = doc.createElement('style');
        const nonce = getCspNonce({ document: doc });
        if (nonce) {
            dynamicStyleElement.nonce = nonce;
        }
        dynamicStyleElement.textContent = ':where(:root) {}';
        doc.head.appendChild(dynamicStyleElement);
        dynamicStyleSheet = dynamicStyleElement.sheet;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('DOM', 'Failed to initialize dynamic stylesheet.', runtimeError);
        dynamicStyleElement = null;
    }
    return dynamicStyleSheet;
};

const removeDynamicStyle = (element: Element, propertyKey: string): void => {
    const state = elementStyleState.get(element);
    if (!state) return;

    const existing = state.get(propertyKey);
    if (!existing) return;
    if (!element.classList) {
        throw new Error('Element.classList is required for dynamic styles');
    }

    element.classList.remove(existing.className);
    state.delete(propertyKey);
    if (state.size === 0) {
        elementStyleState.delete(element);
    }
};

const registerDynamicStyleRule = (propertyKey: string, cssValue: string): string | null => {
    const key = `${propertyKey}:${cssValue}`;
    const cached = dynamicStyleRuleCache.get(key);
    if (cached) return cached;

    const sheet = ensureDynamicStyleSheet();
    if (!sheet) return null;

    const className = `${STYLE_NAMESPACE}-${(dynamicStyleRuleCache.size + 1).toString(36)}`;
    const finalValue = cssValue.includes('!important') ? cssValue : `${cssValue} !important`;
    try {
        sheet.insertRule(`.${className}{${propertyKey}: ${finalValue};}`, sheet.cssRules.length);
        dynamicStyleRuleCache.set(key, className);
        return className;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('DOM', `Failed to register style rule for ${propertyKey}`, runtimeError);
        throw ensureError(error);
    }
};

const applyDynamicStyle = (element: Element, property: string, value: string | null): void => {
    if (!isElementNode(element)) return;

    if (!element.classList) {
        throw new Error('Element.classList is required for dynamic styles');
    }

    const propertyKey = normalizeCssPropertyName(property);
    if (!propertyKey) return;

    if (value === null || value === undefined || value === '') {
        removeDynamicStyle(element, propertyKey);
        return;
    }

    const cssValue = sanitizeCssValue(value);
    if (!cssValue) {
        removeDynamicStyle(element, propertyKey);
        return;
    }

    const className = registerDynamicStyleRule(propertyKey, cssValue);
    if (!className) return;

    const state = elementStyleState.get(element) ?? new Map<string, StyleState>();
    const existing = state.get(propertyKey);
    if (existing?.className === className) return;

    if (existing) {
        element.classList.remove(existing.className);
    }

    element.classList.add(className);
    state.set(propertyKey, { className, value: cssValue });
    elementStyleState.set(element, state);
};

const getDynamicStyleValue = (element: Element, property: string): string => {
    if (!isElementNode(element)) return '';
    const propertyKey = normalizeCssPropertyName(property);
    if (!propertyKey) return '';

    const state = elementStyleState.get(element);
    if (state?.has(propertyKey)) {
        return state.get(propertyKey)?.value ?? '';
    }

    const win = getDomWindow();
    if (isFunction(win?.getComputedStyle)) {
        return win.getComputedStyle(element).getPropertyValue(propertyKey) ?? '';
    }

    return '';
};

const captureScrollState = (element: HTMLElement): ScrollStateEntry[] => {
    if (!isHTMLElement(element)) return [];
    if (element.scrollTop === 0 && element.scrollLeft === 0) return [];

    const canScroll = (element.scrollHeight > element.clientHeight && element.clientHeight > 0) || (element.scrollWidth > element.clientWidth && element.clientWidth > 0);

    if (!canScroll) return [];

    return [
        {
            element,
            top: element.scrollTop,
            left: element.scrollLeft
        }
    ];
};

const restoreScrollState = (entries: ScrollStateEntry[]): void => {
    if (!entries.length) {
        return;
    }

    const applyState = (): void => {
        for (const entry of entries) {
            const target = entry.element;
            if (!isHTMLElement(target)) continue;
            if (target.scrollTop !== entry.top) {
                target.scrollTop = entry.top;
            }
            if (target.scrollLeft !== entry.left) {
                target.scrollLeft = entry.left;
            }
        }
    };

    const requestAnimationFrame = getRequestAnimationFrame();
    requestAnimationFrame(() => {
        requestAnimationFrame(applyState);
    });
};

export { applyDynamicStyle, captureScrollState, getDynamicStyleValue, restoreScrollState };
