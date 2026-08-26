/* SoAI - Shared pagehost actions [frontend/assets/ts/core/pagehost/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { ErrorHandler } from '@core/errorHandler.ts';
import { isPageOutletSlot, removeNonPageOutletSlotNodes } from '@core/pageoutlet/slots.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { isFunction, isHTMLElement, isObject, isString } from '@core/typeGuards.ts';
import type { CleanupMethodName, PageHostDomApi, PageInstance } from '@core/pagehost/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

const resolveDom = (): PageHostDomApi | null => dom;

const resolveContainer = (target: HTMLElement | string | null | undefined, domResolver: () => PageHostDomApi | null): HTMLElement | null => {
    if (isHTMLElement(target)) {
        return target;
    }
    if (!isString(target)) {
        return null;
    }
    const trimmed = target.trim();
    if (!trimmed) {
        return null;
    }
    const domModule = domResolver();
    if (!domModule) {
        return null;
    }
    const resolveHtml = (selector: string): HTMLElement | null => {
        const resolved = domModule.resolve(selector);
        return resolved instanceof HTMLElement ? resolved : null;
    };
    if (trimmed.startsWith('#') || trimmed.startsWith('.')) {
        return resolveHtml(trimmed);
    }
    return resolveHtml(`#${trimmed}`) || resolveHtml(trimmed);
};

const runCleanupMethods = async (instance: PageInstance, methods: readonly CleanupMethodName[], hostErrorHandler: ErrorHandler): Promise<void> => {
    const failures: Error[] = [];
    for (const method of methods) {
        try {
            if (method === 'cleanup') {
                if (!isFunction(instance.cleanup)) {
                    continue;
                }
                await Promise.resolve(instance.cleanup());
                continue;
            }
            if (!isFunction(instance.destroy)) {
                continue;
            }
            await Promise.resolve(instance.destroy());
        } catch (error) {
            const runtimeError = ensureError(error);
            failures.push(runtimeError);
            hostErrorHandler.warn('PageHost', `Cleanup method "${method}" failed`, runtimeError);
        }
    }
    if (failures.length > 0) {
        throw new AggregateError(failures, 'Page cleanup failed');
    }
};

const prepareInstance = (instance: PageInstance, container: HTMLElement): void => {
    if (isFunction(instance.setContainer)) {
        instance.setContainer(container);
        return;
    }
    if (instance.container !== container) {
        instance.container = container;
    }
};

const prepareContainer = (container: HTMLElement, name: string, domResolver: () => PageHostDomApi | null): void => {
    const preserveSlots = container.dataset['pageOutletRoot'] === 'true';
    if (preserveSlots) {
        removeNonPageOutletSlotNodes(container);
    } else {
        const domModule = domResolver();
        if (domModule && isObject(domModule) && isFunction(domModule.setHTML)) {
            domModule.setHTML(container, EMPTY_UI_HTML, { escape: false });
        } else {
            container.textContent = '';
        }
    }
    container.dataset['activePage'] = name;
};

const createPreparedPageContainer = (container: HTMLElement): HTMLElement => {
    const preparedContainer = container.cloneNode(false);
    if (!isHTMLElement(preparedContainer)) {
        throw new Error('PageHost could not create an isolated preparation container');
    }
    delete preparedContainer.dataset['activePage'];
    delete preparedContainer.dataset['pageOutletState'];
    delete preparedContainer.dataset['routeSkeleton'];
    preparedContainer.dataset['pageHostPrepared'] = 'true';
    preparedContainer.removeAttribute('aria-busy');
    return preparedContainer;
};

const commitPreparedPageContainer = (container: HTMLElement, preparedContainer: HTMLElement): HTMLElement => {
    const previousContainer = createPreparedPageContainer(container);
    const previousNodes = Array.from(container.childNodes).filter((node) => !isPageOutletSlot(node));
    const preparedNodes = Array.from(preparedContainer.childNodes).filter((node) => !isPageOutletSlot(node));
    const firstSlot = Array.from(container.childNodes).find(isPageOutletSlot) ?? null;
    try {
        previousNodes.forEach((node) => previousContainer.append(node));
        preparedNodes.forEach((node) => container.insertBefore(node, firstSlot));
    } catch (error) {
        preparedNodes.forEach((node) => preparedContainer.append(node));
        previousNodes.forEach((node) => container.insertBefore(node, firstSlot));
        throw ensureError(error);
    }
    const activePage = preparedContainer.dataset['activePage'];
    if (activePage) {
        container.dataset['activePage'] = activePage;
    } else {
        delete container.dataset['activePage'];
    }
    return previousContainer;
};

export { commitPreparedPageContainer, createPreparedPageContainer, prepareContainer, prepareInstance, resolveContainer, resolveDom, runCleanupMethods };
