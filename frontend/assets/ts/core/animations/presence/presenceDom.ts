/* SoAI - Presence-animated DOM insertion and removal [frontend/assets/ts/core/animations/presence/presenceDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isLayoutParentRendered, isRendered } from '@core/animations/presence/presenceGeometry.ts';
import { exitWithPresence, isPresenceExiting, prepareEnterWithPresence, requestPresenceEnter } from '@core/animations/presence/presenceTransitions.ts';

const detachElement = (element: HTMLElement): void => {
    element.remove();
};

const insertWithPresence = (parent: Element, element: HTMLElement, before: Node | null = null, animate = true): void => {
    if (isPresenceExiting(element)) {
        if (element.parentNode !== parent) {
            parent.insertBefore(element, before);
        }
        prepareEnterWithPresence(element, animate && element.ownerDocument.visibilityState === 'visible' && isRendered(element) && isLayoutParentRendered(element))();
        return;
    }
    if (element.parentNode === parent) {
        return;
    }
    requestPresenceEnter(element, animate);
    parent.insertBefore(element, before);
};

const removeWithPresence = (element: HTMLElement): void => {
    if (element.ownerDocument.visibilityState !== 'visible' || !isRendered(element) || !isLayoutParentRendered(element)) {
        detachElement(element);
        return;
    }
    exitWithPresence(element, null, detachElement);
};

const resolveNextPresenceAnchor = (node: ChildNode): ChildNode | null => {
    let next = node.nextSibling;
    while (next instanceof HTMLElement && isPresenceExiting(next)) {
        next = next.nextSibling;
    }
    return next;
};

export { insertWithPresence, removeWithPresence, resolveNextPresenceAnchor };
