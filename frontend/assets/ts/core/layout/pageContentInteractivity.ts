/* SoAI - Composed page availability and document-modal isolation [frontend/assets/ts/core/layout/pageContentInteractivity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';

interface PageContentIsolation {
    readonly ariaHidden: string | null;
}

interface PageContentInteractivity {
    available: boolean;
    inertWhenAvailable: boolean;
    isolation: PageContentIsolation | null;
    ready: boolean | null;
    inputBlocks: Set<symbol>;
}

const contentStates = new WeakMap<Element, PageContentInteractivity>();

const getContentState = (content: Element): PageContentInteractivity => {
    let state = contentStates.get(content);
    if (!state) {
        state = { available: true, inertWhenAvailable: content.hasAttribute('inert'), isolation: null, ready: null, inputBlocks: new Set() };
        contentStates.set(content, state);
    }
    return state;
};

const synchronizeContentInteractivity = (content: Element, state: PageContentInteractivity): void => {
    content.toggleAttribute('inert', !state.available || state.isolation !== null || state.inertWhenAvailable || state.ready === false || state.inputBlocks.size > 0);
};

const captureAvailableInertState = (content: Element, state: PageContentInteractivity): void => {
    if (state.available && state.isolation === null && state.ready !== false && state.inputBlocks.size === 0) state.inertWhenAvailable = content.hasAttribute('inert');
};

const isPageContentAvailable = (content: Element): boolean => contentStates.get(content)?.available ?? true;

const hasPageContentInputBarrier = (content: Element): boolean => {
    const state = contentStates.get(content);
    return state ? state.inputBlocks.size > 0 || state.isolation !== null || state.inertWhenAvailable : content.hasAttribute('inert');
};

const setPageContentAvailable = (content: Element, available: boolean): void => {
    const state = getContentState(content);
    captureAvailableInertState(content, state);
    state.available = available;
    synchronizeContentInteractivity(content, state);
    content.classList.toggle(CSS_CLASSES.HIDDEN, !available);
};

const setPageContentReady = (content: Element, ready: boolean): void => {
    const state = getContentState(content);
    if (state.ready === null) state.inertWhenAvailable = false;
    state.ready = ready;
    synchronizeContentInteractivity(content, state);
};

const blockPageContentInput = (content: Element): (() => void) => {
    const state = getContentState(content);
    captureAvailableInertState(content, state);
    const block = Symbol('page-content-input');
    state.inputBlocks.add(block);
    synchronizeContentInteractivity(content, state);
    return () => {
        if (!state.inputBlocks.delete(block)) return;
        synchronizeContentInteractivity(content, state);
    };
};

const isolatePageContent = (content: Element): (() => void) => {
    const state = getContentState(content);
    if (state.isolation !== null) throw new Error('Page content already has a document-modal isolation owner');
    captureAvailableInertState(content, state);
    const isolation: PageContentIsolation = { ariaHidden: content.getAttribute('aria-hidden') };
    state.isolation = isolation;
    synchronizeContentInteractivity(content, state);
    content.setAttribute('aria-hidden', 'true');
    return () => {
        if (state.isolation !== isolation) return;
        state.isolation = null;
        synchronizeContentInteractivity(content, state);
        if (isolation.ariaHidden === null) content.removeAttribute('aria-hidden');
        else content.setAttribute('aria-hidden', isolation.ariaHidden);
    };
};

export { blockPageContentInput, hasPageContentInputBarrier, isPageContentAvailable, setPageContentAvailable, setPageContentReady, isolatePageContent };
