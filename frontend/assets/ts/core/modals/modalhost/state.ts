/* SoAI - Shared modals modalhost state [frontend/assets/ts/core/modals/modalhost/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
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
    const page = dom.resolve('.page-scrollable');
    const content = requirePageContentRegion();
    const snapshot: ModalPageLockSnapshot = {
        contentAriaHidden: content.getAttribute('aria-hidden'),
        contentInert: content.hasAttribute('inert'),
        bodyModalLocked: body.getAttribute('data-modal-page-locked'),
        bodyOverflow: body.style.overflow,
        pageOverflow: page instanceof HTMLElement ? page.style.overflow : null
    };
    body.setAttribute('data-modal-page-locked', 'true');
    content.setAttribute('inert', '');
    content.setAttribute('aria-hidden', 'true');
    body.style.overflow = 'hidden';
    if (page instanceof HTMLElement) {
        page.style.overflow = 'hidden';
    }
    return snapshot;
};

const restorePage = (snapshot: ModalPageLockSnapshot | null): void => {
    const page = dom.resolve('.page-scrollable');
    const body = dom.getBody();
    const content = requirePageContentRegion();
    if (snapshot) {
        if (snapshot.bodyModalLocked === null) {
            body.removeAttribute('data-modal-page-locked');
        } else {
            body.setAttribute('data-modal-page-locked', snapshot.bodyModalLocked);
        }
        if (snapshot.contentInert) {
            content.setAttribute('inert', '');
        } else {
            content.removeAttribute('inert');
        }
        if (snapshot.contentAriaHidden === null) {
            content.removeAttribute('aria-hidden');
        } else {
            content.setAttribute('aria-hidden', snapshot.contentAriaHidden);
        }
        body.style.overflow = snapshot.bodyOverflow;
        if (page instanceof HTMLElement) {
            page.style.overflow = snapshot.pageOverflow === null ? '' : snapshot.pageOverflow;
        }
        return;
    }
    body.removeAttribute('data-modal-page-locked');
    content.removeAttribute('inert');
    content.removeAttribute('aria-hidden');
    body.style.overflow = '';
    if (page instanceof HTMLElement) {
        page.style.overflow = '';
    }
};

export { lockPage, restorePage };
