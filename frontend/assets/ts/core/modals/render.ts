/* SoAI - Shared modals render [frontend/assets/ts/core/modals/render.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { resolveModalLayoutContract } from '@core/modals/layoutPresets.ts';
import type { ModalConfig, ModalLayoutPreset } from '@core/modals/types.ts';

const getModalOverlay = (modal: Element): Element | null => dom.resolve('.modal-overlay', modal);
const getModalContent = (modal: Element): Element | null => dom.resolve('.modal-content', modal);

const prepareModalLayoutState = (modal: Element): void => {
    const content = getModalContent(modal);
    dom.removeClass(modal, 'u-hidden');
    if (content) {
        dom.removeClass(content, 'u-hidden');
    }
};

const setModalOpenState = (modal: Element, isOpen: boolean): void => {
    const overlay = getModalOverlay(modal);
    const content = getModalContent(modal);
    const action = isOpen ? dom.removeClass : dom.addClass;

    action(modal, 'u-hidden');
    if (overlay) action(overlay, 'u-hidden');
    if (content) action(content, 'u-hidden');

    if (isOpen) {
        modal.setAttribute('aria-hidden', 'false');
        modal.setAttribute('data-modal-open', 'true');
        if (modal instanceof HTMLElement) {
            void modal.offsetHeight;
        }
    } else {
        modal.setAttribute('aria-hidden', 'true');
        modal.removeAttribute('data-modal-open');
    }
};

const applyBehaviorAttributes = (modal: Element, config: ModalConfig, layoutOverride?: ModalLayoutPreset | undefined): void => {
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
