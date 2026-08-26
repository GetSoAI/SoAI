/* SoAI - Shared modals validation [frontend/assets/ts/core/modals/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const MODAL_ID_REGEX = /^[a-z0-9]+(?:-[a-z0-9]+)*-modal$/;
const MODAL_ROOT_CLASS = 'ui-modal';
const MODAL_ROOT_MARKER_ATTR = 'data-soai-modal-root';

export const normalizeModalId = (id: string): string => {
    const trimmed = id.trim();
    if (!trimmed) {
        throw new Error('Modal id must be non-empty');
    }
    if (!MODAL_ID_REGEX.test(trimmed)) {
        throw new Error(`Modal id must be kebab-case and end with "-modal" (received "${trimmed}")`);
    }
    return trimmed;
};

export const validateModalRootContract = (element: HTMLElement, id: string): void => {
    const modalId = normalizeModalId(id);
    if (!element.hasAttribute(MODAL_ROOT_MARKER_ATTR) || !element.classList.contains(MODAL_ROOT_CLASS)) {
        throw new Error(`Modal "${modalId}" root must include ${MODAL_ROOT_MARKER_ATTR} and class "${MODAL_ROOT_CLASS}"`);
    }
};

export { MODAL_ROOT_CLASS, MODAL_ROOT_MARKER_ATTR };
