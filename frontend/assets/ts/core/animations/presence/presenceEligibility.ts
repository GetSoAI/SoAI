/* SoAI - Presence eligibility for suspended surfaces and modal sessions [frontend/assets/ts/core/animations/presence/presenceEligibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MODAL_ROOT_CLASS } from '@core/modals/guards.ts';

const interactiveModals = new WeakSet<Element>();
const PRESENCE_EXCLUDED_SURFACES = '.ui-round-button, .prompt-card, .plugin-card, .model-card, .hardware-network-card, .search-results .search-item, .file-explorer-rows-body';
const PRESENCE_ATOMIC_ATTRIBUTE = 'data-presence-atomic';
const PRESENCE_VISUAL_ONLY_ATTRIBUTE = 'data-presence-visual-only';
const PRESENCE_MORPH_ATTRIBUTE = 'data-presence-morph';

const isPresenceAtomic = (element: Element): boolean => element.hasAttribute(PRESENCE_ATOMIC_ATTRIBUTE);

const canAnimatePresence = (element: Element, options: { allowAtomicMorph?: boolean } = {}): boolean => {
    const atomicParent = element.parentElement?.closest(`[${PRESENCE_ATOMIC_ATTRIBUTE}]`);
    const atomicChildRequestsMotion = (isPresenceAtomic(element) && element.hasAttribute('data-presence')) || element.hasAttribute(PRESENCE_VISUAL_ONLY_ATTRIBUTE) || (options.allowAtomicMorph === true && element.hasAttribute(PRESENCE_MORPH_ATTRIBUTE));
    if (element.closest('[data-presence-suspended]') || element.closest(PRESENCE_EXCLUDED_SURFACES) || (atomicParent && !atomicChildRequestsMotion)) return false;
    const modal = element.closest(`.${MODAL_ROOT_CLASS}`);
    return !modal || element === modal || (modal.getAttribute('data-modal-open') === 'true' && interactiveModals.has(modal));
};

const resetModalPresence = (modal: Element): void => {
    interactiveModals.delete(modal);
};

const recordModalPresenceInteraction = (event: Event): void => {
    if (!event.isTrusted || !(event.target instanceof Element)) {
        return;
    }
    const modal = event.target.closest(`.${MODAL_ROOT_CLASS}`);
    if (modal?.getAttribute('data-modal-open') === 'true') {
        interactiveModals.add(modal);
    }
};

export { canAnimatePresence, isPresenceAtomic, recordModalPresenceInteraction, resetModalPresence };
