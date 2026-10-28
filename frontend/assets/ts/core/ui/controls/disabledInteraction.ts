/* SoAI - Disabled control activation containment [frontend/assets/ts/core/ui/controls/disabledInteraction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';

const createDisabledInteractionService = (documentRef: Document) => {
    let cleanup: (() => void) | null = null;
    const preventDisabledActivation = (event: Event): void => {
        if (!(event.target instanceof Element)) return;
        const disabledControl = event.target.closest('[aria-disabled="true"]');
        if (!disabledControl || disabledControl.getAttribute('data-toggle-disabled') === 'true') return;
        if (event instanceof KeyboardEvent && event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        event.stopImmediatePropagation();
    };
    return {
        initialize(): void {
            if (cleanup) return;
            cleanup = bindEventGroup(['click', 'auxclick', 'dblclick', 'pointerdown', 'keydown'].map((type) => ({ target: documentRef, type, listener: preventDisabledActivation, options: true })));
        },
        destroy(): void {
            cleanup?.();
            cleanup = null;
        }
    };
};

export { createDisabledInteractionService };
