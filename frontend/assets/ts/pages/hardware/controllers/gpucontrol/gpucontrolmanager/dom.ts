/* SoAI - Hardware page GPU control manager DOM contracts [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { createHtmlFragment } from '@core/dom/html.ts';

export const getDataAttribute = (element: Element, attr: string): string | null => element.getAttribute(`data-${attr}`);

export const setDataAttribute = (element: Element, attr: string, value: string): void => {
    element.setAttribute(`data-${attr}`, value);
};

export const createElementFromMarkup = (document: Document, markup: string): Element => {
    const fragment = createHtmlFragment({ documentRef: document, html: markup, context: document });
    const element = fragment.firstElementChild;
    if (!element) {
        throw new Error('GPU controls markup did not produce an element');
    }
    return element;
};

const resolveGpuControlsSection = (documentRef: Document): HTMLElement | null => {
    const section = dom.resolve('#gpu-control-section', documentRef);
    return section instanceof HTMLElement ? section : null;
};

const resolveGpuControlsContainer = (documentRef: Document): HTMLElement | null => {
    const container = dom.resolve('#gpu-controls-container', documentRef);
    return container instanceof HTMLElement ? container : null;
};

export const syncGpuControlsPanelVisibility = (documentRef: Document, visible: boolean): void => {
    const section = resolveGpuControlsSection(documentRef);
    if (section) {
        section.classList.toggle('u-hidden', !visible);
    }
};

export const clearGpuControlsPanel = (documentRef: Document): void => {
    const container = resolveGpuControlsContainer(documentRef);
    if (container) {
        container.replaceChildren();
    }
};
