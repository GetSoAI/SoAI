/* SoAI - Pointer dismissal of transient action control focus [frontend/assets/ts/core/ui/controls/pointerFocus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';

const ACTION_FOCUS_SELECTOR = "button, select, a[href], summary, input:is([type='button'], [type='submit'], [type='reset'], [type='checkbox'], [type='radio']), :is([role='button'], [role='tab'], [role='switch'], [role='menuitem'], [role='combobox'], [role='link'], [role='checkbox'], [role='radio']):not(input, textarea, [contenteditable])";

const createPointerFocusService = (documentRef: Document) => {
    let cleanup: (() => void) | null = null;

    const dismissActionFocus = (event: Event): void => {
        if (!(event instanceof PointerEvent) || event.button !== 0 || !event.isPrimary) return;
        const active = documentRef.activeElement;
        if (!(active instanceof HTMLElement) || active.isContentEditable || !active.matches(ACTION_FOCUS_SELECTOR)) return;
        const target = event.target;
        if (!(target instanceof Element) || event.composedPath().includes(active)) return;
        const label = target.closest('label');
        if (label instanceof HTMLLabelElement && label.control === active) return;
        active.blur();
    };

    return {
        initialize(): void {
            if (cleanup) return;
            cleanup = bindEventGroup([{ target: documentRef, type: 'pointerdown', listener: dismissActionFocus, options: true }]);
        },
        destroy(): void {
            cleanup?.();
            cleanup = null;
        }
    };
};

export { createPointerFocusService };
