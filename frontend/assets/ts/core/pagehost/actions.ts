/* SoAI - Shared pagehost actions [frontend/assets/ts/core/pagehost/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { ErrorHandler } from '@core/errorHandler.ts';
import { isPageOutletSlot, removeNonPageOutletSlotNodes } from '@core/pageoutlet/slots.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { isFunction, isHTMLElement, isObject, isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { CleanupMethodName, PageHostDomApi, PageInstance, PreparedPageState } from '@core/pagehost/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { blockPageContentInput } from '@core/layout/pageContentInteractivity.ts';

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

interface PageContainerBindings {
    previous: PageInstance | null;
    incoming: PageInstance;
    commit?: () => void;
    rollback?: () => void;
}

class PageContainerRollbackError extends AggregateError {
    readonly inputAdmissions: readonly (() => void)[];
    constructor(errors: readonly Error[], message: string, inputAdmissions: readonly (() => void)[] = []) {
        super(errors, message);
        this.inputAdmissions = inputAdmissions;
    }
}

const commitPreparedPageContainer = (container: HTMLElement, preparedContainer: HTMLElement, bindings?: PageContainerBindings): HTMLElement => {
    const previousContainer = createPreparedPageContainer(container);
    const previousNodes = Array.from(container.childNodes).filter((node) => !isPageOutletSlot(node));
    const preparedNodes = Array.from(preparedContainer.childNodes).filter((node) => !isPageOutletSlot(node));
    const firstSlot = Array.from(container.childNodes).find(isPageOutletSlot) ?? null;
    const previousActivePage = container.dataset['activePage'];
    let publicationAttempted = false;
    const inputAdmissions: (() => void)[] = [];
    let retainInputAdmission = false;
    try {
        for (const node of previousNodes) if (node instanceof Element) inputAdmissions.push(blockPageContentInput(node));
        previousNodes.forEach((node) => previousContainer.append(node));
        preparedNodes.forEach((node) => container.insertBefore(node, firstSlot));
        if (bindings?.previous) prepareInstance(bindings.previous, previousContainer);
        if (bindings) prepareInstance(bindings.incoming, container);
        publicationAttempted = true;
        bindings?.commit?.();
    } catch (error) {
        const failures: Error[] = [];
        const restore = (operation: () => void): void => {
            try {
                operation();
            } catch (failure) {
                failures.push(ensureError(failure));
            }
        };
        for (const node of preparedNodes) restore(() => preparedContainer.append(node));
        for (const node of previousNodes) restore(() => container.insertBefore(node, firstSlot));
        if (bindings?.previous)
            restore(() => {
                if (bindings.previous) prepareInstance(bindings.previous, container);
            });
        if (bindings) restore(() => prepareInstance(bindings.incoming, preparedContainer));
        if (publicationAttempted && bindings?.rollback) restore(bindings.rollback);
        if (previousActivePage === undefined) delete container.dataset['activePage'];
        else container.dataset['activePage'] = previousActivePage;
        if (failures.length) {
            retainInputAdmission = true;
            throw new PageContainerRollbackError([ensureError(error), ...failures], 'Page container restoration incomplete', inputAdmissions);
        }
        throw ensureError(error);
    } finally {
        if (!retainInputAdmission) for (const release of inputAdmissions) release();
    }
    const activePage = preparedContainer.dataset['activePage'];
    if (activePage) {
        container.dataset['activePage'] = activePage;
    } else {
        delete container.dataset['activePage'];
    }
    return previousContainer;
};

const initializePreparedPage = async (prepared: PreparedPageState, parameters: JsonObject, isCurrent: () => boolean): Promise<void> => {
    const { instance } = prepared;
    if (!isFunction(instance.initialize)) {
        throw new Error('Page instance missing initialize method');
    }
    await Promise.resolve(instance.initialize(parameters));
    if (!isCurrent()) {
        return;
    }
    let preparedTask: Promise<void> = Promise.resolve();
    let viewReadyTask: Promise<void> = Promise.resolve();
    let dataReadyTask: Promise<void> = Promise.resolve();
    if (instance.pageLifecycle) {
        preparedTask = Promise.resolve(instance.pageLifecycle.whenReady({ waitForReveal: false }));
        viewReadyTask = Promise.resolve(instance.pageLifecycle.whenReady({ waitForData: false }));
        dataReadyTask = Promise.resolve(instance.pageLifecycle.whenReady({ waitForData: true }));
    }
    prepared.preparedPromise = preparedTask;
    prepared.viewReadyPromise = viewReadyTask;
    prepared.dataReadyPromise = dataReadyTask;
    prepared.isPreparationComplete = true;
};

export { initializePreparedPage, commitPreparedPageContainer, createPreparedPageContainer, PageContainerRollbackError, prepareContainer, prepareInstance, resolveContainer, resolveDom, runCleanupMethods };
