/* SoAI - Shared modals modalhost state [frontend/assets/ts/core/modals/modalhost/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getMutationObserverCtor } from '@core/environment/public.ts';
import { isolatePageContent } from '@core/layout/pageContentInteractivity.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import type { ModalPageLockSnapshot } from '@core/modals/modalhost/types.ts';

const requirePageContentRegion = (): HTMLElement => {
    const content = dom.resolve('#main-content');
    if (!(content instanceof HTMLElement)) {
        throw new Error('Page content region is required for modal page isolation');
    }
    return content;
};

const lockPage = (): ModalPageLockSnapshot => {
    const body = dom.getBody();
    const content = requirePageContentRegion();
    const scrollRoots: ModalPageLockSnapshot['scrollRoots'] = new Map();
    const lockScrollRoot = (element: HTMLElement): void => {
        if (scrollRoots.has(element)) return;
        const overflow = element.style.getPropertyValue('overflow');
        const priority = element.style.getPropertyPriority('overflow');
        scrollRoots.set(element, { overflow, priority });
        element.style.setProperty('overflow', 'hidden', priority);
    };
    const lockSubtreeScrollRoots = (root: Element): void => {
        if (root instanceof HTMLElement && root.matches('.page-scrollable')) lockScrollRoot(root);
        for (const element of dom.resolveAll('.page-scrollable', root)) if (element instanceof HTMLElement) lockScrollRoot(element);
    };
    const Observer = getMutationObserverCtor();
    const observer = new Observer((records) => {
        for (const record of records) {
            if (record.type === 'childList') {
                for (const node of record.addedNodes) if (node instanceof Element && content.contains(node)) lockSubtreeScrollRoots(node);
            } else if (record.target instanceof HTMLElement && content.contains(record.target) && record.target.matches('.page-scrollable')) lockScrollRoot(record.target);
        }
        for (const [element, original] of scrollRoots) {
            if (element === body || (content.contains(element) && element.matches('.page-scrollable'))) continue;
            element.style.setProperty('overflow', original.overflow, original.priority);
            scrollRoots.delete(element);
        }
    });
    const releaseContent = isolatePageContent(content);
    const snapshot: ModalPageLockSnapshot = {
        body,
        bodyModalLocked: body.getAttribute('data-modal-page-locked'),
        releaseContent,
        scrollRoots,
        observer,
        released: false
    };
    try {
        observer.observe(content, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
        body.setAttribute('data-modal-page-locked', 'true');
        lockScrollRoot(body);
        lockSubtreeScrollRoots(content);
    } catch (error) {
        restorePage(snapshot);
        throw error;
    }
    return snapshot;
};

const restorePage = (snapshot: ModalPageLockSnapshot | null): void => {
    if (!snapshot || snapshot.released) return;
    snapshot.released = true;
    const failures: Error[] = [];
    runCleanupStepCollectingFailure(() => snapshot.observer.disconnect(), failures);
    runCleanupStepCollectingFailure(snapshot.releaseContent, failures);
    const body = snapshot.body;
    runCleanupStepCollectingFailure(() => {
        if (snapshot.bodyModalLocked === null) {
            body.removeAttribute('data-modal-page-locked');
        } else {
            body.setAttribute('data-modal-page-locked', snapshot.bodyModalLocked);
        }
    }, failures);
    for (const [element, original] of snapshot.scrollRoots) runCleanupStepCollectingFailure(() => element.style.setProperty('overflow', original.overflow, original.priority), failures);
    snapshot.scrollRoots.clear();
    throwCollectedCleanupFailures(failures);
};

export { lockPage, restorePage };
