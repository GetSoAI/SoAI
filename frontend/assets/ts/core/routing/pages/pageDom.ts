/* SoAI - Shared routing page DOM [frontend/assets/ts/core/routing/pages/pageDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { checkerboardService } from '@core/dom/dom.ts';
import { hasFunctionProperty, isElementNode, isObject, isString } from '@core/typeGuards.ts';

const SIMPLE_UI_SELECTOR_PATTERN = /^[A-Za-z0-9_-]+$/;
type PageDomTarget = string | Element | readonly (string | Element)[] | null | undefined;

const createPageDomError = (message: string): Error => new Error(message);

const normalizeUISelector = (selector: string): string => {
    const trimmedSelector = selector.trim();
    return !trimmedSelector || /^[#.[\]:]|[\s>+~,]/.test(trimmedSelector) ? trimmedSelector : SIMPLE_UI_SELECTOR_PATTERN.test(trimmedSelector) ? `#${trimmedSelector}` : trimmedSelector;
};

const extractElementId = (selector: PageDomTarget): string | null => {
    if (!isString(selector)) return null;
    const trimmedSelector = selector.trim();
    return trimmedSelector && trimmedSelector.startsWith('#') ? trimmedSelector.slice(1) : SIMPLE_UI_SELECTOR_PATTERN.test(trimmedSelector) && !/[#.\s>+~,:[\]]/.test(trimmedSelector) ? trimmedSelector : null;
};

export const normalizeSelectorInput = (target: PageDomTarget): PageDomTarget => (isString(target) ? normalizeUISelector(target) : Array.isArray(target) ? target.map((item) => (isString(item) ? normalizeUISelector(item) : item)) : target);

export const normalizeSelectorForResolve = (target: PageDomTarget): PageDomTarget => {
    if (isElementNode(target)) return target;
    const elementId = extractElementId(target);
    return elementId ? `#${elementId}` : (normalizeSelectorInput(target) ?? target);
};

const normalizeSelectorEntry = (target: string | Element): string | Element => {
    const normalized = normalizeSelectorForResolve(target);
    if (isString(normalized) || isElementNode(normalized)) {
        return normalized;
    }
    return target;
};

export const normalizeSelectorList = (target: PageDomTarget): PageDomTarget => (Array.isArray(target) ? target.map(normalizeSelectorEntry) : normalizeSelectorForResolve(target));

type CheckerboardServiceApi = {
    applyCheckerboard: (container: Element, selector?: string, absoluteIndexOffset?: number) => void;
    updateCheckerboard: (container: Element, selector?: string, absoluteIndexOffset?: number) => void;
    disconnect: (id: string) => void;
    getContainerId: (container: Element) => string;
};

const isCheckerboardServiceApi = <T>(value: T): value is T & CheckerboardServiceApi => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperty(value, 'applyCheckerboard') && hasFunctionProperty(value, 'updateCheckerboard') && hasFunctionProperty(value, 'disconnect') && hasFunctionProperty(value, 'getContainerId');
};

export const getOptionalCheckerboardService = (): CheckerboardServiceApi | null => {
    return isCheckerboardServiceApi(checkerboardService) ? checkerboardService : null;
};

export const requireCheckerboardService = (): CheckerboardServiceApi => {
    const service = getOptionalCheckerboardService();
    if (!service) throw createPageDomError('Checkerboard service is unavailable');
    return service;
};
