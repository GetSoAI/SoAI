/* SoAI - Shared modals render [frontend/assets/ts/core/modals/render.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { exitWithPresence, prepareEnterWithPresence } from '@core/animations/presence/public.ts';
import { resolveModalLayoutContract } from '@core/modals/layoutPresets.ts';
import type { ModalConfig, ModalLayoutPreset } from '@core/modals/types.ts';

const getModalOverlay = (modal: Element): Element | null => dom.resolve('.modal-overlay', modal);
const getModalContent = (modal: Element): Element | null => dom.resolve('.modal-content', modal);

const prepareModalLayoutState = (modal: Element): void => {
    modal.setAttribute('data-presence-visual-only', '');
    const content = getModalContent(modal);
    dom.removeClass(modal, 'u-hidden');
    if (content) {
        dom.removeClass(content, 'u-hidden');
    }
};

const setModalOpenState = (modal: Element, isOpen: boolean, onClosed?: () => void): void => {
    const overlay = getModalOverlay(modal);
    const content = getModalContent(modal);
    const action = isOpen ? dom.removeClass : dom.addClass;
    const wasOpen = modal.getAttribute('data-modal-open') === 'true';
    const viewport = modal.getAttribute('data-modal-presentation') === 'viewport';
    const start = !viewport && isOpen && !wasOpen && modal instanceof HTMLElement ? prepareEnterWithPresence(modal, true, true) : null;
    const closingWithPresence = !viewport && !isOpen && wasOpen && modal instanceof HTMLElement;

    if (closingWithPresence) {
        exitWithPresence(modal, 'flex', () => {
            if (overlay) dom.addClass(overlay, 'u-hidden');
            if (content) dom.addClass(content, 'u-hidden');
            onClosed?.();
        });
    }

    action(modal, 'u-hidden');
    if (overlay && (isOpen || !wasOpen)) action(overlay, 'u-hidden');
    if (content && !closingWithPresence) action(content, 'u-hidden');

    if (isOpen) {
        modal.setAttribute('aria-hidden', 'false');
        modal.setAttribute('data-modal-open', 'true');
        if (!viewport && modal instanceof HTMLElement) {
            void modal.offsetHeight;
        }
        start?.();
    } else {
        modal.setAttribute('aria-hidden', 'true');
        modal.removeAttribute('data-modal-open');
        if (!closingWithPresence) onClosed?.();
    }
};

const applyBehaviorAttributes = (modal: Element, config: ModalConfig, layoutOverride?: ModalLayoutPreset | undefined): void => {
    modal.setAttribute('data-modal-presentation', config.presentation);
    const content = getModalContent(modal);
    const layout = layoutOverride === undefined ? config : resolveModalLayoutContract(layoutOverride);
    const apply = (element: Element | null): void => {
        if (!element) {
            return;
        }
        element.setAttribute('data-modal-resizable', String(config.resizable));
        element.setAttribute('data-modal-dynamic', String(config.dynamic));
    };
    apply(modal);
    apply(content);

    if (content) {
        content.setAttribute('data-modal-size', layout.size);
    }
};

export { applyBehaviorAttributes, prepareModalLayoutState, setModalOpenState };
