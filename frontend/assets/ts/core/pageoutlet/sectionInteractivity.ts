/* SoAI - Shared page outlet section interactivity [frontend/assets/ts/core/pageoutlet/sectionInteractivity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getMutationObserverCtor } from '@core/environment/public.ts';
import { PAGE_CONTENT_READY } from '@core/pageTransitions.ts';

const isPageSection = (node: Node): node is Element => node instanceof Element && node.hasAttribute('data-section');

const syncSectionInteractivity = (section: Element): void => {
    const interactive = section.classList.contains(PAGE_CONTENT_READY);
    if (section.hasAttribute('inert') === interactive) {
        section.toggleAttribute('inert', !interactive);
    }
};

const trackSection = (observer: MutationObserver, node: Node): void => {
    if (!isPageSection(node)) {
        return;
    }
    syncSectionInteractivity(node);
    observer.observe(node, { attributes: true, attributeFilter: ['class'] });
};

const observePageSectionInteractivity = (container: HTMLElement): (() => void) => {
    const MutationObserverConstructor = getMutationObserverCtor();
    let observer: MutationObserver;
    observer = new MutationObserverConstructor((records) => {
        for (const record of records) {
            if (record.type === 'childList') {
                record.addedNodes.forEach((node) => trackSection(observer, node));
            } else if (record.target.parentNode === container && isPageSection(record.target)) {
                syncSectionInteractivity(record.target);
            }
        }
    });
    observer.observe(container, { childList: true });
    container.childNodes.forEach((node) => trackSection(observer, node));
    return () => observer.disconnect();
};

export { observePageSectionInteractivity };
